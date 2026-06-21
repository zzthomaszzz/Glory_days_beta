# All ability classes; AbilityBase defines the interface every ability must implement.
# Cross-module imports (server.projectiles, server.entities, server.game_state,
# shared.map_data) are deferred inside methods: entities.py imports this file at
# the top level, so importing them back here at module level creates circular cycles.
import math

# ---------------------------------------------------------------------------
# ABILITY_STATS — all tunable numbers in one place.
# To rebalance an ability, change its entry here; the class reads from it.
# ---------------------------------------------------------------------------
ABILITY_STATS = {
    'Snipe': dict(
        cooldown=20.0, mana_cost=120, channel_time=2.5,
        shot_damage=225, true_sight_dur=3.0, cast_range=300,
    ),
    'Fireball': dict(
        cooldown=11.0, mana_cost=80, cast_range=150, aoe_size=64,
        base_tick_damage=40, ap_ratio=0.6,
        ba_duration=4.0, ba_tick_interval=0.5, proj_speed=350,
    ),
    'Fortify': dict(
        cooldown=12.0, mana_cost=60, armor_bonus=50, mr_bonus=50,
        duration=5.0, regen_per_sec=20.0,
    ),
    'Mend': dict(
        cooldown=5.5, mana_cost=0, hp_cost=50, heal_amount=100, cast_range=120,
    ),
    'GroundSlam': dict(
        cooldown=8.0, mana_cost=60, slam_radius=100, slam_damage=50,
        slow_factor=0.7, slow_duration=2.0, ring_speed=350.0,
    ),
    'Charge': dict(
        cooldown=10.0, mana_cost=80, cast_range=2150, damage=50, stun_dur=1,
    ),
    'Dash': dict(
        cooldown=3.0, mana_cost=30, dash_range=80,
    ),
    'Teleport': dict(
        cooldown=18.0, mana_cost=80, channel_time=1.5, cast_range=300,
        pulse_damage=80, pulse_max_range=150, pulse_speed=150.0,
    ),
    'PlaceTurret': dict(
        cooldown=10.0, mana_cost=50, max_turrets=2, place_range=50,
        turret_hp=150, turret_armor=7, turret_atk_range=120, turret_atk_dmg=25,
        turret_atk_speed=1.5, turret_proj_speed=200,
    ),
    'Spin': dict(
        cooldown=15.0, mana_cost=80, spin_duration=5.0, spin_radius=80,
        tick_damage=25, tick_interval=0.5,
    ),
    'Bushido': dict(
        cooldown=0.0, mana_cost=0, crit_chance=0.25, crit_mult=1.4,
    ),
    'Stealth': dict(
        cooldown=20.0, mana_cost=60, duration=10.0, bonus_mult=1.4,
    ),
    'PlaceTrap': dict(
        cooldown=5.0, mana_cost=20, max_traps=2, place_range=200,
        trap_root_dur=2.0, trap_bleed_dps=80, trap_bleed_dur=2.0,
        trap_sight_dur=3.0, trap_trigger_r=20, trap_size=16,
    ),
    'Bolt': dict(
        cooldown=20.0, mana_cost=70, damage=200, speed=175.0,
    ),
    'Recall': dict(
        cooldown=8.0, mana_cost=0, channel_time=4.0,
    ),
    'PlaceBanner': dict(
        cooldown=30.0, mana_cost=100, place_range=60,
        banner_duration=10.0, banner_heal_radius=100, banner_heal_pct_sec=0.02,
    ),
    'Hook': dict(
        cooldown=14.0, mana_cost=60, channel_time=0.6,
        speed=600, max_range=250, hit_radius=22,
        pull_dist=60, pull_dur=0.3, damage=120, stun_dur=1,
    ),
    'IronStack': dict(
        cooldown=0.0, mana_cost=0, max_stacks=10, armor_per_stack=5, stack_duration=5.0,
    ),
    'BattleCry': dict(
        cooldown=20.0, mana_cost=50, radius=200, speed_bonus=40, duration=3.0,
    ),
}


class AbilityBase:
    cooldown  = 0.0
    mana_cost = 0

    def __init__(self):
        self.cooldown_timer = 0.0
        self.is_on_cooldown = False

    def update(self, dt):
        if self.is_on_cooldown:
            self.cooldown_timer -= dt
            if self.cooldown_timer <= 0:
                self.is_on_cooldown = False

    def can_use(self, player):
        return not self.is_on_cooldown and player.mana >= self.mana_cost

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        player.mana -= self.mana_cost
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        self.activate(player, targets)
        return True

    def activate(self, player, targets):
        pass

    def to_dict(self):
        return {
            "name":           self.__class__.__name__,
            "cooldown_timer": round(self.cooldown_timer, 2),
            "is_on_cooldown": self.is_on_cooldown,
        }


#-------------------------------------------------------------------------------------------------------------------Snipe
class Snipe(AbilityBase):
    _s             = ABILITY_STATS['Snipe']
    cooldown       = _s['cooldown']
    mana_cost      = _s['mana_cost']
    channel_time   = _s['channel_time']
    shot_damage    = _s['shot_damage']
    true_sight_dur = _s['true_sight_dur']
    cast_range     = _s['cast_range']

    def __init__(self):
        super().__init__()
        self.is_channeling    = False
        self.channel_timer    = 0.0
        self.target_id        = None
        self.true_sight_timer = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if not targets or game_state is None:
            return False
        target = game_state.players.get(targets[0])
        if not target or target.is_dead:
            return False
        ddx = target.x - player.x
        ddy = target.y - player.y
        if ddx*ddx + ddy*ddy > self.cast_range**2:
            return False
        player.mana          -= self.mana_cost
        self.is_on_cooldown   = True
        self.cooldown_timer   = self.cooldown
        self.is_channeling    = True
        self.channel_timer    = self.channel_time
        self.target_id        = targets[0]
        self.true_sight_timer = self.true_sight_dur
        return True

    def tick(self, dt, player, game_state):
        if self.true_sight_timer > 0:
            self.true_sight_timer = max(0.0, self.true_sight_timer - dt)
        if self.is_channeling:
            self.channel_timer -= dt
            if self.channel_timer <= 0:
                self.is_channeling    = False
                self._fire(player, game_state)
                self.true_sight_timer = self.true_sight_dur

    def _fire(self, player, game_state):
        from server.projectiles import Projectile  # avoids circular import
        target = game_state.players.get(self.target_id)
        if not target or target.is_dead:
            return
        pid = game_state._proj_counter[0]
        game_state._proj_counter[0] += 1
        game_state.projectiles[pid] = Projectile(
            proj_id=pid,
            owner_id=player.id,
            owner_team=player.team,
            x=player.x, y=player.y,
            target_type="player",
            target_id=self.target_id,
            damage=self.shot_damage,
            armor=0,
            speed=player.proj_speed * 2,
        )

    def to_dict(self):
        d = super().to_dict()
        d["is_targeted"]      = True
        d["is_channeling"]    = self.is_channeling
        d["channel_timer"]    = round(self.channel_timer, 2)
        d["channel_time"]     = self.channel_time
        d["target_id"]        = self.target_id
        d["true_sight_timer"] = round(self.true_sight_timer, 2)
        d["cast_range"]       = self.cast_range
        return d


#-------------------------------------------------------------------------------------------------------------------Fireball
class Fireball(AbilityBase):
    _s               = ABILITY_STATS['Fireball']
    cooldown         = _s['cooldown']
    mana_cost        = _s['mana_cost']
    cast_range       = _s['cast_range']
    aoe_size         = _s['aoe_size']
    base_tick_damage = _s['base_tick_damage']
    ap_ratio         = _s['ap_ratio']
    ba_duration      = _s['ba_duration']
    ba_tick_interval = _s['ba_tick_interval']
    proj_speed       = _s['proj_speed']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if dx*dx + dy*dy > self.cast_range**2:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.activate(player, targets, target_pos, game_state)
        return True

    def activate(self, player, targets, target_pos=None, game_state=None):
        from server.projectiles import FireballProjectile  # avoids circular import
        tx, ty = target_pos
        tick_damage = self.base_tick_damage + int(player.ability_power * self.ap_ratio)
        pid = game_state._proj_counter[0]
        game_state._proj_counter[0] += 1
        game_state.fireball_projectiles[pid] = FireballProjectile(
            proj_id=pid,
            owner_team=player.team,
            x=player.x, y=player.y,
            target_x=tx, target_y=ty,
            tick_damage=tick_damage,
            ba_size=self.aoe_size,
            ba_duration=self.ba_duration,
            ba_tick_interval=self.ba_tick_interval,
            speed=self.proj_speed,
        )

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.cast_range
        d["aoe_size"]     = self.aoe_size
        return d


#-------------------------------------------------------------------------------------------------------------------Fortify
class Fortify(AbilityBase):
    _s            = ABILITY_STATS['Fortify']
    cooldown      = _s['cooldown']
    mana_cost     = _s['mana_cost']
    armor_bonus   = _s['armor_bonus']
    mr_bonus      = _s['mr_bonus']
    duration      = _s['duration']
    regen_per_sec = _s['regen_per_sec']

    def __init__(self):
        super().__init__()
        self.is_active      = False
        self.duration_timer = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_active       = True
        self.duration_timer  = self.duration
        player.armor        += self.armor_bonus
        player.magic_resist += self.mr_bonus
        return True

    def tick(self, dt, player, game_state):
        if not self.is_active:
            return
        self.duration_timer -= dt
        player.hp = min(player.max_hp, player.hp + self.regen_per_sec * dt)
        if self.duration_timer <= 0:
            self.is_active       = False
            self.duration_timer  = 0.0
            player.armor        -= self.armor_bonus
            player.magic_resist -= self.mr_bonus

    def to_dict(self):
        d = super().to_dict()
        d["is_active"]      = self.is_active
        d["duration_timer"] = round(self.duration_timer, 2)
        d["duration"]       = self.duration
        return d


#-------------------------------------------------------------------------------------------------------------------Mend
class Mend(AbilityBase):
    _s          = ABILITY_STATS['Mend']
    cooldown    = _s['cooldown']
    mana_cost   = _s['mana_cost']
    hp_cost     = _s['hp_cost']
    heal_amount = _s['heal_amount']
    cast_range  = _s['cast_range']

    def can_use(self, player):
        return not self.is_on_cooldown and player.hp > self.hp_cost

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if not targets or game_state is None:
            return False
        target = game_state.players.get(targets[0])
        if not target or target.is_dead or target.team != player.team or target is player:
            return False
        ddx = target.x - player.x
        ddy = target.y - player.y
        if ddx * ddx + ddy * ddy > self.cast_range ** 2:
            return False
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        player.hp  -= self.hp_cost
        target.hp   = min(target.max_hp, target.hp + self.heal_amount)
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_targeted"]      = True
        d["is_ally_targeted"] = True
        d["cast_range"]       = self.cast_range
        return d


#-------------------------------------------------------------------------------------------------------------------GroundSlam
class GroundSlam(AbilityBase):
    _s            = ABILITY_STATS['GroundSlam']
    cooldown      = _s['cooldown']
    mana_cost     = _s['mana_cost']
    slam_radius   = _s['slam_radius']
    slam_damage   = _s['slam_damage']
    slow_factor   = _s['slow_factor']
    slow_duration = _s['slow_duration']
    ring_speed    = _s['ring_speed']

    def __init__(self):
        super().__init__()
        self._ring_active = False
        self._ring_radius = 0.0
        self._ring_x      = 0.0
        self._ring_y      = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        from server.projectiles import apply_damage  # avoids circular import
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self._ring_active    = True
        self._ring_radius    = 0.0
        self._ring_x         = player.x
        self._ring_y         = player.y
        r2 = self.slam_radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team == player.team:
                continue
            dx, dy = p.x - player.x, p.y - player.y
            if dx * dx + dy * dy <= r2:
                apply_damage(p, self.slam_damage, p.armor, killer=player)
                p.slow_timer  = self.slow_duration
                p.slow_factor = self.slow_factor
        return True

    def tick(self, dt, player, game_state):
        if not self._ring_active:
            return
        self._ring_radius += self.ring_speed * dt
        if self._ring_radius >= self.slam_radius:
            self._ring_active = False

    def to_dict(self):
        d = super().to_dict()
        d["ring_active"] = self._ring_active
        d["ring_radius"] = round(self._ring_radius, 1)
        d["ring_x"]      = round(self._ring_x, 1)
        d["ring_y"]      = round(self._ring_y, 1)
        return d


#-------------------------------------------------------------------------------------------------------------------Charge
class Charge(AbilityBase):
    _s         = ABILITY_STATS['Charge']
    cooldown   = _s['cooldown']
    mana_cost  = _s['mana_cost']
    cast_range = _s['cast_range']
    damage     = _s['damage']
    stun_dur   = _s['stun_dur']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        if not targets:
            return False
        target = game_state.players.get(targets[0])
        if not target or target.is_dead or target.team == player.team:
            return False
        dx, dy = target.x - player.x, target.y - player.y
        if dx * dx + dy * dy > self.cast_range ** 2:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self._charge(player, target)
        return True

    def _charge(self, player, target):
        import pygame  # map_data imports pygame; deferred to keep server startup lean
        from shared.map_data import OBSTACLES
        from server.projectiles import apply_damage  # avoids circular import
        dx, dy = target.x - player.x, target.y - player.y
        dist   = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        ux, uy    = dx / dist, dy / dist
        stop_dist = max(0, dist - player.size)
        steps     = max(1, int(stop_dist))
        half      = player.size // 2
        nx, ny    = player.x, player.y
        for _ in range(steps):
            tx2 = nx + ux
            ty2 = ny + uy
            pr  = pygame.Rect(int(tx2 - half), int(ty2 - half), player.size, player.size)
            if any(obs.colliderect(pr) for obs in OBSTACLES):
                break
            nx, ny = tx2, ty2
        player.x, player.y = nx, ny
        apply_damage(target, self.damage, target.armor, killer=player)
        target.stun_timer = self.stun_dur

    def to_dict(self):
        d = super().to_dict()
        d["is_targeted"] = True
        d["cast_range"]  = self.cast_range
        return d


#-------------------------------------------------------------------------------------------------------------------Dash
class Dash(AbilityBase):
    _s         = ABILITY_STATS['Dash']
    cooldown   = _s['cooldown']
    mana_cost  = _s['mana_cost']
    dash_range = _s['dash_range']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self._dash(player, target_pos)
        return True

    def _dash(self, player, target_pos):
        import pygame  # map_data imports pygame; deferred to keep server startup lean
        from shared.map_data import OBSTACLES
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        raw    = math.sqrt(dx * dx + dy * dy)
        if raw < 1:
            return
        dist   = min(raw, self.dash_range)
        ux, uy = dx / raw, dy / raw
        steps  = max(1, int(dist))    # 1-unit steps for precise wall stopping
        half   = player.size // 2
        nx, ny = player.x, player.y
        for _ in range(steps):
            tx2 = nx + ux
            ty2 = ny + uy
            pr  = pygame.Rect(int(tx2 - half), int(ty2 - half), player.size, player.size)
            if any(obs.colliderect(pr) for obs in OBSTACLES):
                break
            nx, ny = tx2, ty2
        player.x = nx
        player.y = ny

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.dash_range
        return d


#-------------------------------------------------------------------------------------------------------------------Teleport
class Teleport(AbilityBase):
    _s              = ABILITY_STATS['Teleport']
    cooldown        = _s['cooldown']
    mana_cost       = _s['mana_cost']
    channel_time    = _s['channel_time']
    cast_range      = _s['cast_range']
    pulse_damage    = _s['pulse_damage']
    pulse_max_range = _s['pulse_max_range']
    pulse_speed     = _s['pulse_speed']

    def __init__(self):
        super().__init__()
        self.is_channeling  = False
        self.channel_timer  = 0.0
        self.target_pos     = None
        self._hp_snapshot   = 0.0
        self._pulse_active  = False
        self._pulse_radius  = 0.0
        self._pulse_x       = 0.0
        self._pulse_y       = 0.0
        self._pulse_hit_ids = set()

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if dx * dx + dy * dy > self.cast_range ** 2:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_channeling   = True
        self.channel_timer   = self.channel_time
        self.target_pos      = target_pos
        self._hp_snapshot    = player.hp
        return True

    def tick(self, dt, player, game_state):
        if self.is_channeling:
            if player.hp < self._hp_snapshot:
                self.is_channeling = False
                self.target_pos    = None
                return
            self.channel_timer -= dt
            if self.channel_timer <= 0:
                self.is_channeling = False
                if self.target_pos:
                    player.x, player.y  = self.target_pos
                    self._pulse_active  = True
                    self._pulse_radius  = 0.0
                    self._pulse_x       = player.x
                    self._pulse_y       = player.y
                    self._pulse_hit_ids = set()
                self.target_pos = None

        if self._pulse_active and game_state is not None:
            from server.projectiles import apply_damage  # avoids circular import
            old_r              = self._pulse_radius
            self._pulse_radius = min(self.pulse_max_range,
                                     self._pulse_radius + self.pulse_speed * dt)
            new_r              = self._pulse_radius
            for p in game_state.players.values():
                if p.is_dead or p.team == player.team or p.id in self._pulse_hit_ids:
                    continue
                dx   = p.x - self._pulse_x
                dy   = p.y - self._pulse_y
                dist = math.sqrt(dx * dx + dy * dy)
                if old_r <= dist <= new_r:
                    apply_damage(p, self.pulse_damage, p.magic_resist, killer=player)
                    self._pulse_hit_ids.add(p.id)
            if self._pulse_radius >= self.pulse_max_range:
                self._pulse_active = False
                self._pulse_hit_ids.clear()

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"]  = True
        d["place_range"]   = self.cast_range
        d["is_channeling"] = self.is_channeling
        d["channel_timer"] = round(self.channel_timer, 2)
        d["channel_time"]  = self.channel_time
        d["pulse_active"]  = self._pulse_active
        d["pulse_radius"]  = round(self._pulse_radius, 1)
        d["pulse_x"]       = round(self._pulse_x, 1)
        d["pulse_y"]       = round(self._pulse_y, 1)
        return d


#-------------------------------------------------------------------------------------------------------------------PlaceTurret
class PlaceTurret(AbilityBase):
    _s                = ABILITY_STATS['PlaceTurret']
    cooldown          = _s['cooldown']
    mana_cost         = _s['mana_cost']
    max_turrets       = _s['max_turrets']
    place_range       = _s['place_range']
    turret_hp         = _s['turret_hp']
    turret_armor      = _s['turret_armor']
    turret_atk_range  = _s['turret_atk_range']
    turret_atk_dmg    = _s['turret_atk_dmg']
    turret_atk_speed  = _s['turret_atk_speed']
    turret_proj_speed = _s['turret_proj_speed']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if dx*dx + dy*dy > self.place_range ** 2:
            return False
        count = sum(
            1 for t in game_state.player_turrets.values()
            if t.owner_id == player.id and not t.is_destroyed
        )
        if count >= self.max_turrets:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.activate(player, targets, target_pos, game_state)
        return True

    def activate(self, player, targets, target_pos=None, game_state=None):
        from server.buildings import PlayerTurret  # avoids circular import
        tx, ty = target_pos
        tid = game_state._turret_counter[0]
        game_state._turret_counter[0] += 1
        game_state.player_turrets[tid] = PlayerTurret(
            tid, player.id, player.team, tx, ty,
            hp         = self.turret_hp,
            armor      = self.turret_armor,
            atk_range  = self.turret_atk_range,
            atk_dmg    = self.turret_atk_dmg,
            atk_speed  = self.turret_atk_speed,
            proj_speed = self.turret_proj_speed,
        )

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.place_range
        return d


#-------------------------------------------------------------------------------------------------------------------Spin
class Spin(AbilityBase):
    _s            = ABILITY_STATS['Spin']
    cooldown      = _s['cooldown']
    mana_cost     = _s['mana_cost']
    spin_duration = _s['spin_duration']
    spin_radius   = _s['spin_radius']
    tick_damage   = _s['tick_damage']
    tick_interval = _s['tick_interval']

    def __init__(self):
        super().__init__()
        self.is_spinning = False
        self.spin_timer  = 0.0
        self.tick_timer  = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_spinning     = True
        self.spin_timer      = self.spin_duration
        self.tick_timer      = 0.0
        return True

    def tick(self, dt, player, game_state):
        if not self.is_spinning:
            return
        self.spin_timer -= dt
        self.tick_timer += dt
        if self.tick_timer >= self.tick_interval:
            self.tick_timer -= self.tick_interval
            self._deal_tick(player, game_state)
        if self.spin_timer <= 0:
            self.is_spinning = False
            self.spin_timer  = 0.0

    def _deal_tick(self, player, game_state):
        from server.projectiles import apply_damage  # avoids circular import
        r2 = self.spin_radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team == player.team:
                continue
            dx, dy = p.x - player.x, p.y - player.y
            if dx * dx + dy * dy <= r2:
                apply_damage(p, self.tick_damage, p.armor, killer=player)

    def to_dict(self):
        d = super().to_dict()
        d["is_spinning"]   = self.is_spinning
        d["spin_timer"]    = round(self.spin_timer, 2)
        d["spin_duration"] = self.spin_duration
        d["slam_radius"]   = self.spin_radius
        return d


#-------------------------------------------------------------------------------------------------------------------Bushido
class Bushido(AbilityBase):
    _s          = ABILITY_STATS['Bushido']
    cooldown    = _s['cooldown']
    mana_cost   = _s['mana_cost']
    crit_chance = _s['crit_chance']
    crit_mult   = _s['crit_mult']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        return False

    def to_dict(self):
        d = super().to_dict()
        d["is_passive"]  = True
        d["crit_chance"] = self.crit_chance
        return d


#-------------------------------------------------------------------------------------------------------------------Stealth
class Stealth(AbilityBase):
    _s         = ABILITY_STATS['Stealth']
    cooldown   = _s['cooldown']
    mana_cost  = _s['mana_cost']
    duration   = _s['duration']
    bonus_mult = _s['bonus_mult']

    def __init__(self):
        super().__init__()
        self.is_active      = False
        self.duration_timer = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        player.mana               -= self.mana_cost
        self.is_on_cooldown        = True
        self.cooldown_timer        = self.cooldown
        self.is_active             = True
        self.duration_timer        = self.duration
        player.is_invisible        = True
        player._stealth_bonus_ready = True
        return True

    def tick(self, dt, player, game_state):
        if not self.is_active:
            return
        self.duration_timer -= dt
        if self.duration_timer <= 0:
            self.is_active      = False
            self.duration_timer = 0.0
            player.is_invisible = False

    def to_dict(self):
        d = super().to_dict()
        d["is_active"]      = self.is_active
        d["duration_timer"] = round(self.duration_timer, 2)
        d["duration"]       = self.duration
        return d


#-------------------------------------------------------------------------------------------------------------------PlaceTrap
class PlaceTrap(AbilityBase):
    _s             = ABILITY_STATS['PlaceTrap']
    cooldown       = _s['cooldown']
    mana_cost      = _s['mana_cost']
    max_traps      = _s['max_traps']
    place_range    = _s['place_range']
    trap_root_dur  = _s['trap_root_dur']
    trap_bleed_dps = _s['trap_bleed_dps']
    trap_bleed_dur = _s['trap_bleed_dur']
    trap_sight_dur = _s['trap_sight_dur']
    trap_trigger_r = _s['trap_trigger_r']
    trap_size      = _s['trap_size']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if dx * dx + dy * dy > self.place_range ** 2:
            return False
        count = sum(1 for t in game_state.traps.values()
                    if t.owner_id == player.id and not t.is_expired)
        if count >= self.max_traps:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        from server.entities import Trap  # avoids circular import
        tid = game_state._trap_counter[0]
        game_state._trap_counter[0] += 1
        game_state.traps[tid] = Trap(
            tid, player.id, player.team, tx, ty,
            root_dur  = self.trap_root_dur,
            bleed_dps = self.trap_bleed_dps,
            bleed_dur = self.trap_bleed_dur,
            sight_dur = self.trap_sight_dur,
            trigger_r = self.trap_trigger_r,
            size      = self.trap_size,
        )
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.place_range
        return d


#-------------------------------------------------------------------------------------------------------------------Bolt
class Bolt(AbilityBase):
    _s        = ABILITY_STATS['Bolt']
    cooldown  = _s['cooldown']
    mana_cost = _s['mana_cost']
    damage    = _s['damage']
    speed     = _s['speed']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if math.sqrt(dx * dx + dy * dy) < 1:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        from server.projectiles import BoltProjectile  # avoids circular import
        bid = game_state._proj_counter[0]
        game_state._proj_counter[0] += 1
        game_state.bolt_projectiles[bid] = BoltProjectile(
            proj_id=bid, owner_id=player.id, owner_team=player.team,
            x=player.x, y=player.y, dx=dx, dy=dy,
            damage=self.damage, speed=self.speed,
        )
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = 9999
        return d


#-------------------------------------------------------------------------------------------------------------------Recall
class Recall(AbilityBase):
    _s           = ABILITY_STATS['Recall']
    cooldown     = _s['cooldown']
    mana_cost    = _s['mana_cost']
    channel_time = _s['channel_time']

    def __init__(self):
        super().__init__()
        self.is_channeling = False
        self.channel_timer = 0.0
        self._hp_snapshot  = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if self.is_channeling:
            self._cancel()
            return True
        self.is_channeling = True
        self.channel_timer = self.channel_time
        self._hp_snapshot  = player.hp
        return True

    def tick(self, dt, player, game_state):
        if not self.is_channeling:
            return
        # Interrupted by damage, CC, or intentional movement
        if player.hp < self._hp_snapshot:
            self._cancel()
            return
        if player.stun_timer > 0 or player.slow_timer > 0:
            self._cancel()
            return
        if player.dx != 0 or player.dy != 0:
            self._cancel()
            return
        self.channel_timer -= dt
        if self.channel_timer <= 0:
            self._complete(player, game_state)

    def _cancel(self):
        self.is_channeling = False
        self.channel_timer = 0.0

    def _complete(self, player, game_state):
        from server.game_state import SPAWN_POSITIONS  # avoids circular import
        self.is_channeling   = False
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        player.x, player.y  = SPAWN_POSITIONS.get(player.team, (60.0, 60.0))
        player.attack_target = None

    def to_dict(self):
        d = super().to_dict()
        d["is_channeling"] = self.is_channeling
        d["channel_timer"] = round(self.channel_timer, 2)
        d["channel_time"]  = self.channel_time
        d["is_recall"]     = True
        return d


#-------------------------------------------------------------------------------------------------------------------PlaceBanner
class PlaceBanner(AbilityBase):
    _s                  = ABILITY_STATS['PlaceBanner']
    cooldown            = _s['cooldown']
    mana_cost           = _s['mana_cost']
    place_range         = _s['place_range']
    banner_duration     = _s['banner_duration']
    banner_heal_radius  = _s['banner_heal_radius']
    banner_heal_pct_sec = _s['banner_heal_pct_sec']

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if dx * dx + dy * dy > self.place_range ** 2:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        from server.buildings import Banner  # avoids circular import
        bid = game_state._banner_counter[0]
        game_state._banner_counter[0] += 1
        game_state.banners[bid] = Banner(
            bid, player.id, player.team, tx, ty,
            duration     = self.banner_duration,
            heal_radius  = self.banner_heal_radius,
            heal_pct_sec = self.banner_heal_pct_sec,
        )
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.place_range
        return d


#-------------------------------------------------------------------------------------------------------------------Hook
class Hook(AbilityBase):
    _s           = ABILITY_STATS['Hook']
    cooldown     = _s['cooldown']
    mana_cost    = _s['mana_cost']
    channel_time = _s['channel_time']

    def __init__(self):
        super().__init__()
        self.is_channeling = False
        self.channel_timer = 0.0
        self._cast_dx      = 0.0
        self._cast_dy      = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or target_pos is None:
            return False
        dx = target_pos[0] - player.x
        dy = target_pos[1] - player.y
        if dx == 0 and dy == 0:
            dx = 1
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_channeling   = True
        self.channel_timer   = self.channel_time
        self._cast_dx        = dx
        self._cast_dy        = dy
        return True

    def tick(self, dt, player, game_state):
        if not self.is_channeling:
            return
        self.channel_timer -= dt
        if self.channel_timer <= 0:
            self.is_channeling = False
            self._fire(player, game_state)

    def _fire(self, player, game_state):
        from server.projectiles import HookProjectile  # avoids circular import
        pid = game_state._proj_counter[0]
        game_state._proj_counter[0] += 1
        game_state.hook_projectiles[pid] = HookProjectile(
            pid, player.id, player.team,
            player.x, player.y,
            self._cast_dx, self._cast_dy,
        )

    def to_dict(self):
        d = super().to_dict()
        d["is_point_cast"]  = True
        d["cast_range"]     = ABILITY_STATS['Hook']['max_range']
        d["is_channeling"]  = self.is_channeling
        d["channel_timer"]  = round(self.channel_timer, 2)
        d["channel_time"]   = self.channel_time
        return d


#-------------------------------------------------------------------------------------------------------------------IronStack
class IronStack(AbilityBase):
    _s              = ABILITY_STATS['IronStack']
    cooldown        = _s['cooldown']
    mana_cost       = _s['mana_cost']
    MAX_STACKS      = _s['max_stacks']
    ARMOR_PER_STACK = _s['armor_per_stack']
    STACK_DURATION  = _s['stack_duration']

    def __init__(self):
        super().__init__()
        self.stacks      = 0
        self.stack_timer = 0.0

    def on_auto_hit(self, player):
        if self.stacks < self.MAX_STACKS:
            player.armor += self.ARMOR_PER_STACK
        self.stacks      = min(self.stacks + 1, self.MAX_STACKS)
        self.stack_timer = self.STACK_DURATION

    def tick(self, dt, player, game_state):
        if self.stacks == 0:
            return
        self.stack_timer -= dt
        if self.stack_timer <= 0:
            player.armor     -= self.stacks * self.ARMOR_PER_STACK
            self.stacks       = 0
            self.stack_timer  = 0.0

    def can_use(self, player):
        return False

    def to_dict(self):
        d = super().to_dict()
        d["is_passive"]  = True
        d["stacks"]      = self.stacks
        d["max_stacks"]  = self.MAX_STACKS
        return d


#-------------------------------------------------------------------------------------------------------------------BattleCry
class BattleCry(AbilityBase):
    _s          = ABILITY_STATS['BattleCry']
    cooldown    = _s['cooldown']
    mana_cost   = _s['mana_cost']
    radius      = _s['radius']
    speed_bonus = _s['speed_bonus']
    duration    = _s['duration']

    def __init__(self):
        super().__init__()
        self.is_active      = False
        self.duration_timer = 0.0
        self._buffed_ids    = []

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_active       = True
        self.duration_timer  = self.duration
        self._buffed_ids     = []
        r2 = self.radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team != player.team:
                continue
            ddx = p.x - player.x
            ddy = p.y - player.y
            if ddx * ddx + ddy * ddy <= r2:
                p.speed += self.speed_bonus
                self._buffed_ids.append(p.id)
        return True

    def tick(self, dt, player, game_state):
        if not self.is_active:
            return
        self.duration_timer -= dt
        if self.duration_timer <= 0:
            self.is_active = False
            for pid in self._buffed_ids:
                p = game_state.players.get(pid)
                if p:
                    p.speed -= self.speed_bonus
            self._buffed_ids = []

    def to_dict(self):
        d = super().to_dict()
        d["is_active"]      = self.is_active
        d["duration_timer"] = round(self.duration_timer, 2)
        d["duration"]       = self.duration
        return d
