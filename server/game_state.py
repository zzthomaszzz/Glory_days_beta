from server.entities import Player, HERO_REGISTRY, BurningArea
from server.buildings import BuildingHeadquarter, CapturePoint, ShopBuilding
from shared.items import ITEMS
from server.systems.movement import apply_movement
from server.systems.ability import update_abilities
from server.systems.combat import resolve_combat, resolve_turret_combat, update_projectiles
from shared.map_data import CAPTURE_ZONES
from shared.constants import RUNE_X, RUNE_Y, RUNE_RADIUS, RUNE_CAPTURE_TIME, RUNE_RESPAWN_TIME, RUNE_DAMAGE

SPAWN_POSITIONS = {
    1: (60.0, 60.0),
    2: (1220.0, 740.0),
}


class GameState:
    def __init__(self):
        self.players               = {}
        self.winner                = None
        self.projectiles           = {}
        self._proj_counter         = [0]
        self.player_turrets        = {}
        self._turret_counter       = [0]
        self.banners               = {}
        self._banner_counter       = [0]
        self.fireball_projectiles  = {}
        self.burning_areas         = {}
        self._ba_counter           = [0]
        self.buildings = {
            0: BuildingHeadquarter(1, 0, 0),
            1: BuildingHeadquarter(2, 1232, 752),
        }
        self.match_time = 0.0

        # Lobby phase
        self.game_phase      = "waiting"   # "waiting" | "countdown" | "live"
        self.ready_players   = set()
        self.countdown_timer = 3.0
        self.wait_timer      = 0.0

        for i, (x, y) in enumerate(CAPTURE_ZONES):
            bid = i + 2
            self.buildings[bid] = CapturePoint(bid, x, y)

        self.shops = {
            0: ShopBuilding(0, 80,  700),
            1: ShopBuilding(1, 1150, 60),
        }

        self.rune = {
            "state":          "inactive",   # inactive | available | capturing | cooldown
            "capture_timer":  0.0,
            "respawn_timer":  0.0,
            "capturer_team":  None,
        }

    def add_player(self, player_id, team, hero_name="Player"):
        hero_class = HERO_REGISTRY.get(hero_name, Player)
        player = hero_class(player_id, team)
        spawn = SPAWN_POSITIONS[team]
        player.x = spawn[0]
        player.y = spawn[1]
        self.players[player_id] = player

    def remove_player(self, player_id):
        self.players.pop(player_id, None)
        self.ready_players.discard(player_id)

    def apply_input(self, player_id, msg):
        player = self.players.get(player_id)
        if not player or player.is_dead:
            return
        match msg.get("type"):
            case "input":
                player.dx = msg.get("dx", 0)
                player.dy = msg.get("dy", 0)
                if "target_type" in msg:
                    player.attack_target = (msg["target_type"], msg["target_id"])
                if "ability" in msg:
                    slot = msg["ability"]
                    ability = player.abilities[slot] if 0 <= slot < len(player.abilities) else None
                    if ability:
                        tx = msg.get("ability_target_x")
                        ty = msg.get("ability_target_y")
                        target_pos = (tx, ty) if tx is not None and ty is not None else None
                        tid = msg.get("ability_target_id")
                        targets = [int(tid)] if tid is not None else None
                        ability.use(player, targets=targets, target_pos=target_pos, game_state=self)
            case "buy_item":
                self._handle_purchase(player_id, msg)
            case "sell_item":
                self._handle_sell_item(player_id, msg.get("slot", -1))
            case "ready":
                self._handle_ready(player_id)
            case "force_start":
                self._handle_force_start()

    def _handle_purchase(self, player_id, msg):
        player = self.players.get(player_id)
        if not player or player.is_dead:
            return
        item_key = msg.get("item")
        if item_key not in ITEMS:
            return
        item = ITEMS[item_key]
        near = any(
            (player.x - (s.x + s.SIZE // 2)) ** 2 + (player.y - (s.y + s.SIZE // 2)) ** 2 <= s.RANGE ** 2
            for s in self.shops.values()
        )
        if not near:
            return
        if player.gold < item["cost"]:
            return
        empty = next((i for i, slot in enumerate(player.inventory) if slot is None and i < 3), None)
        if empty is None:
            return
        player.gold -= item["cost"]
        player.inventory[empty] = item_key
        for stat, val in item["stats"].items():
            setattr(player, stat, getattr(player, stat, 0) + val)

    def _handle_sell_item(self, player_id, slot):
        player = self.players.get(player_id)
        if not player or player.is_dead:
            return
        if not (0 <= slot < 3):
            return
        item_key = player.inventory[slot]
        if item_key not in ITEMS:
            return
        item = ITEMS[item_key]
        player.inventory[slot] = None
        player.gold += item["cost"] // 2
        for stat, val in item["stats"].items():
            setattr(player, stat, getattr(player, stat, 0) - val)

    def _handle_ready(self, player_id):
        if self.game_phase != "waiting":
            return
        self.ready_players.add(player_id)
        if self.players and all(pid in self.ready_players for pid in self.players):
            self._start_countdown()

    def _handle_force_start(self):
        if self.game_phase == "waiting" and self.wait_timer >= 90.0:
            self._start_countdown()

    def _start_countdown(self):
        self.game_phase      = "countdown"
        self.countdown_timer = 3.0

    def _go_live(self):
        self.game_phase = "live"
        for player in self.players.values():
            spawn = SPAWN_POSITIONS.get(player.team, (60.0, 60.0))
            player.x, player.y   = spawn
            player.hp             = player.max_hp
            player.mana           = player.max_mana
            player.is_dead        = False
            player.respawn_timer  = 0.0
            player.attack_target  = None
            player.stun_timer          = 0.0
            player.slow_timer          = 0.0
            player.slow_factor         = 1.0
            player.armor_reduction     = 0
            player.armor_reduction_timer = 0.0
            for ab in player.abilities:
                if ab:
                    ab.is_on_cooldown = False
                    ab.cooldown_timer = 0.0
                    if hasattr(ab, "is_channeling"):
                        ab.is_channeling = False
                    if hasattr(ab, "is_active"):
                        ab.is_active = False

    def update(self, dt):
        # Phase management
        if self.game_phase == "waiting":
            if self.players:
                self.wait_timer += dt
            for player in self.players.values():
                if player.attack_target and player.attack_target[0] == "building":
                    player.attack_target = None
        elif self.game_phase == "countdown":
            self.countdown_timer -= dt
            if self.countdown_timer <= 0:
                self._go_live()

        # Player status ticks (always — practice is fully active during warmup)
        for player in self.players.values():
            if player.is_dead:
                continue
            if player.hp_regen > 0:
                player.hp = min(player.max_hp, player.hp + player.hp_regen * dt)
            if player.stun_timer > 0:
                player.stun_timer = max(0.0, player.stun_timer - dt)
            if player.slow_timer > 0:
                player.slow_timer = max(0.0, player.slow_timer - dt)
                if player.slow_timer <= 0:
                    player.slow_factor = 1.0
            if player.armor_reduction_timer > 0:
                player.armor_reduction_timer = max(0.0, player.armor_reduction_timer - dt)
                if player.armor_reduction_timer <= 0:
                    player.armor_reduction = 0
        apply_movement(self.players, dt)
        update_abilities(self.players, dt, game_state=self)
        resolve_combat(self.players, self.buildings, self.player_turrets, self.banners, dt, self.projectiles, self._proj_counter)
        resolve_turret_combat(self.player_turrets, self.players, dt, self.projectiles, self._proj_counter)
        update_projectiles(self.projectiles, self.players, self.buildings, self.player_turrets, self.banners, dt)
        for fp in list(self.fireball_projectiles.values()):
            fp.update(dt, self.burning_areas, self._ba_counter)
        self.fireball_projectiles = {k: v for k, v in self.fireball_projectiles.items() if not v.is_done}
        for ba in self.burning_areas.values():
            ba.update(dt, self.players, self.player_turrets)
        self.burning_areas = {k: v for k, v in self.burning_areas.items() if not v.is_expired}
        self._update_banners(dt)
        self._handle_respawns(dt)

        # Live-only: gold income, capture logic, win condition
        if self.game_phase == "live":
            for building in self.buildings.values():
                building.update(dt, self.players)
            self._update_rune(dt)
            self._check_win()

    def _update_rune(self, dt):
        if not self._minerals_exhausted():
            self.rune["state"] = "inactive"
            return

        rune = self.rune

        if rune["state"] == "inactive":
            rune["state"]         = "available"
            rune["capture_timer"] = 0.0
            rune["capturer_team"] = None

        elif rune["state"] == "cooldown":
            rune["respawn_timer"] -= dt
            if rune["respawn_timer"] <= 0:
                rune["state"]         = "available"
                rune["capture_timer"] = 0.0
                rune["capturer_team"] = None

        else:  # available or capturing
            r2 = RUNE_RADIUS ** 2
            teams_present = set()
            for player in self.players.values():
                if player.is_dead:
                    continue
                dx, dy = player.x - RUNE_X, player.y - RUNE_Y
                if dx * dx + dy * dy <= r2:
                    teams_present.add(player.team)

            if not teams_present:
                rune["state"]         = "available"
                rune["capture_timer"] = 0.0
                rune["capturer_team"] = None
            elif len(teams_present) > 1:
                rune["state"] = "capturing"   # contested — timer pauses
            else:
                team = next(iter(teams_present))
                if team != rune["capturer_team"]:
                    rune["capture_timer"] = 0.0
                    rune["capturer_team"] = team
                rune["state"]          = "capturing"
                rune["capture_timer"] += dt
                if rune["capture_timer"] >= RUNE_CAPTURE_TIME:
                    self._trigger_rune(team)

    def _trigger_rune(self, capturing_team):
        import random
        from server.projectiles import apply_damage
        enemy_team    = 2 if capturing_team == 1 else 1
        alive_enemies = [p for p in self.players.values() if p.team == enemy_team and not p.is_dead]
        if alive_enemies:
            apply_damage(random.choice(alive_enemies), RUNE_DAMAGE, 0)
        self.rune["state"]         = "cooldown"
        self.rune["respawn_timer"] = RUNE_RESPAWN_TIME
        self.rune["capture_timer"] = 0.0
        self.rune["capturer_team"] = None

    def _minerals_exhausted(self):
        for b in self.buildings.values():
            if isinstance(b, BuildingHeadquarter):
                if not b.is_destroyed and b.mineral_pool > 0:
                    return False
            elif isinstance(b, CapturePoint):
                if b._mineral_pool > 0:
                    return False
        return True

    def _update_banners(self, dt):
        for banner in self.banners.values():
            banner.update(dt, self.players)
        self.banners = {k: v for k, v in self.banners.items() if not v.is_destroyed}

    def _handle_respawns(self, dt):
        no_respawn = self.game_phase == "live" and self._minerals_exhausted()
        for player in self.players.values():
            if not player.is_dead:
                continue
            if no_respawn:
                continue
            player.respawn_timer -= dt
            if player.respawn_timer <= 0:
                spawn = SPAWN_POSITIONS.get(player.team, (60.0, 60.0))
                player.x = spawn[0]
                player.y = spawn[1]
                player.hp = player.max_hp
                player.mana = player.max_mana
                player.dx = 0
                player.dy = 0
                player.attack_target = None
                player.is_attacking  = False
                player.is_dead       = False

    def _check_win(self):
        if self.winner is not None:
            return
        exhausted = self._minerals_exhausted()
        all_caps_gone = not any(
            isinstance(b, CapturePoint) and not b.is_destroyed
            for b in self.buildings.values()
        )
        for team in (1, 2):
            enemy = 2 if team == 1 else 1
            enemy_hq_down = not any(
                isinstance(b, BuildingHeadquarter) and b.team == enemy and not b.is_destroyed
                for b in self.buildings.values()
            )
            # Annihilation: enemy HQ + all capture zones destroyed
            if enemy_hq_down and all_caps_gone:
                self.winner = team
                return
            # Attrition: minerals exhausted + all enemies permanently dead
            if exhausted:
                enemy_players = [p for p in self.players.values() if p.team == enemy]
                if enemy_players and all(p.is_dead for p in enemy_players):
                    self.winner = team
                    return
