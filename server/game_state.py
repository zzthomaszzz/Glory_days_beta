from server.entities import Player, HERO_REGISTRY
from server.systems.combat import _break_stealth
from server.buildings import BuildingHeadquarter, CapturePoint, ShopBuilding
from server.systems.movement import apply_movement
from server.systems.ability import update_abilities
from server.systems.combat import resolve_combat, resolve_turret_combat
from server.systems.effects import update_effects
from server.systems.status import tick_player_status
from server.systems.rune import update_rune
from server.systems.shop import handle_purchase, handle_sell
from shared.map_data import CAPTURE_ZONES

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
        self.traps                 = {}
        self._trap_counter         = [0]
        self.bolt_projectiles      = {}
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
                elif player.dx != 0 or player.dy != 0:
                    player.attack_target = None
                if "ability" in msg:
                    slot = msg["ability"]
                    ability = player.abilities[slot] if 0 <= slot < len(player.abilities) else None
                    if ability:
                        tx = msg.get("ability_target_x")
                        ty = msg.get("ability_target_y")
                        target_pos = (tx, ty) if tx is not None and ty is not None else None
                        tid = msg.get("ability_target_id")
                        targets = [int(tid)] if tid is not None else None
                        if ability.__class__.__name__ != 'Stealth':
                            _break_stealth(player)
                        ability.use(player, targets=targets, target_pos=target_pos, game_state=self)
            case "buy_item":
                handle_purchase(player, msg.get("item"), self.shops)
            case "sell_item":
                handle_sell(player, msg.get("slot", -1))
            case "ready":
                self._handle_ready(player_id)
            case "force_start":
                self._handle_force_start()

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
            player.root_timer          = 0.0
            player.bleed_timer         = 0.0
            player.bleed_dps           = 0.0
            player.revealed_timer      = 0.0
            player.is_invisible        = False
            player._stealth_bonus_ready = False
            player.bush_idx            = -1
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

        tick_player_status(self.players, dt)
        apply_movement(self.players, dt)
        update_abilities(self.players, dt, game_state=self)
        resolve_combat(self.players, self.buildings, self.player_turrets, self.banners, dt, self.projectiles, self._proj_counter)
        resolve_turret_combat(self.player_turrets, self.players, dt, self.projectiles, self._proj_counter)
        update_effects(
            self.projectiles, self.fireball_projectiles, self.burning_areas, self.banners,
            self.players, self.buildings, self.player_turrets, self._ba_counter, dt,
        )
        for trap in list(self.traps.values()):
            trap.update(dt, self.players)
        self.traps = {k: v for k, v in self.traps.items() if not v.is_expired}
        for bolt in list(self.bolt_projectiles.values()):
            bolt.update(dt, self.players)
        self.bolt_projectiles = {k: v for k, v in self.bolt_projectiles.items() if not v.is_done}
        self._handle_respawns(dt)

        # Live-only: gold income, capture logic, win condition
        if self.game_phase == "live":
            for building in self.buildings.values():
                building.update(dt, self.players)
            update_rune(self.rune, self.players, self._minerals_exhausted(), dt)
            self._check_win()

    def _minerals_exhausted(self):
        for b in self.buildings.values():
            if isinstance(b, BuildingHeadquarter):
                if not b.is_destroyed and b.mineral_pool > 0:
                    return False
            elif isinstance(b, CapturePoint):
                if b._mineral_pool > 0:
                    return False
        return True

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
                player.bush_idx      = -1

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
