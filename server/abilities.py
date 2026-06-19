import math


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
            "name":          self.__class__.__name__,
            "cooldown":      self.cooldown,
            "cooldown_timer": round(self.cooldown_timer, 2),
            "mana_cost":     self.mana_cost,
            "is_on_cooldown": self.is_on_cooldown,
            "is_placement":  False,
        }


#-------------------------------------------------------------------------------------------------------------------Snipe
class Snipe(AbilityBase):
    cooldown       = 30.0
    mana_cost      = 120
    channel_time   = 2.5
    shot_damage    = 225
    true_sight_dur = 3.0
    cast_range     = 250

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
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        self.is_channeling   = True
        self.channel_timer   = self.channel_time
        self.target_id       = targets[0]
        self.true_sight_timer = self.true_sight_dur
        return True

    def tick(self, dt, player, game_state):
        if self.true_sight_timer > 0:
            self.true_sight_timer = max(0.0, self.true_sight_timer - dt)
        if self.is_channeling:
            self.channel_timer -= dt
            if self.channel_timer <= 0:
                self.is_channeling = False
                self._fire(player, game_state)
                self.true_sight_timer = self.true_sight_dur

    def _fire(self, player, game_state):
        from server.projectiles import Projectile
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
    cooldown   = 15.0
    mana_cost  = 80
    cast_range = 150
    aoe_size   = 64

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
        from server.projectiles import FireballProjectile
        tx, ty = target_pos
        tick_damage = 30 + int(player.ability_power * 0.1)
        pid = game_state._proj_counter[0]
        game_state._proj_counter[0] += 1
        game_state.fireball_projectiles[pid] = FireballProjectile(
            proj_id=pid,
            owner_team=player.team,
            x=player.x, y=player.y,
            target_x=tx, target_y=ty,
            tick_damage=tick_damage,
        )

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.cast_range
        d["aoe_size"]     = self.aoe_size
        return d


#-------------------------------------------------------------------------------------------------------------------Fortify
class Fortify(AbilityBase):
    cooldown      = 20.0
    mana_cost     = 60
    armor_bonus   = 30
    mr_bonus      = 30
    duration      = 5.0
    regen_per_sec = 10.0

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
    cooldown     = 5.5
    mana_cost    = 0
    hp_cost      = 50
    heal_amount  = 100
    cast_range   = 120

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
        d["hp_cost"]          = self.hp_cost
        d["heal_amount"]      = self.heal_amount
        return d


#-------------------------------------------------------------------------------------------------------------------GroundSlam
class GroundSlam(AbilityBase):
    cooldown      = 8.0
    mana_cost     = 60
    slam_radius   = 100
    slam_damage   = 50
    slow_factor   = 0.7
    slow_duration = 2.0
    ring_speed    = 350.0

    def __init__(self):
        super().__init__()
        self._ring_active = False
        self._ring_radius = 0.0
        self._ring_x      = 0.0
        self._ring_y      = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        from server.projectiles import apply_damage
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
        d["slam_radius"]   = self.slam_radius
        d["ring_active"]   = self._ring_active
        d["ring_radius"]   = round(self._ring_radius, 1)
        d["ring_x"]        = round(self._ring_x, 1)
        d["ring_y"]        = round(self._ring_y, 1)
        return d


#-------------------------------------------------------------------------------------------------------------------Charge
class Charge(AbilityBase):
    cooldown   = 10.0
    mana_cost  = 80
    cast_range = 200
    damage     = 50
    stun_dur   = 1

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
        import pygame
        from shared.map_data import OBSTACLES
        from server.projectiles import apply_damage
        dx, dy = target.x - player.x, target.y - player.y
        dist   = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        ux, uy     = dx / dist, dy / dist
        stop_dist  = max(0, dist - player.size)
        steps      = max(1, int(stop_dist))
        half       = player.size // 2
        nx, ny     = player.x, player.y
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
    cooldown   = 6.0
    mana_cost  = 50
    dash_range = 120

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
        import pygame
        from shared.map_data import OBSTACLES
        tx, ty  = target_pos
        dx, dy  = tx - player.x, ty - player.y
        raw     = math.sqrt(dx * dx + dy * dy)
        if raw < 1:
            return
        dist    = min(raw, self.dash_range)
        ux, uy  = dx / raw, dy / raw
        steps   = max(1, int(dist))    # 1-unit steps for precise wall stopping
        sx, sy  = ux, uy
        half    = player.size // 2
        nx, ny  = player.x, player.y
        for _ in range(steps):
            tx2 = nx + sx
            ty2 = ny + sy
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
    cooldown        = 18.0
    mana_cost       = 80
    channel_time    = 1.5
    cast_range      = 300
    pulse_damage    = 80
    pulse_max_range = 150
    pulse_speed     = 150.0

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
                self.is_channeling  = False
                if self.target_pos:
                    player.x, player.y = self.target_pos
                    self._pulse_active  = True
                    self._pulse_radius  = 0.0
                    self._pulse_x       = player.x
                    self._pulse_y       = player.y
                    self._pulse_hit_ids = set()
                self.target_pos = None

        if self._pulse_active and game_state is not None:
            from server.projectiles import apply_damage
            old_r              = self._pulse_radius
            self._pulse_radius = min(self.pulse_max_range,
                                     self._pulse_radius + self.pulse_speed * dt)
            new_r              = self._pulse_radius
            for p in game_state.players.values():
                if p.is_dead or p.team == player.team or p.id in self._pulse_hit_ids:
                    continue
                dx = p.x - self._pulse_x
                dy = p.y - self._pulse_y
                dist = math.sqrt(dx * dx + dy * dy)
                if old_r <= dist <= new_r:
                    apply_damage(p, self.pulse_damage, p.magic_resist, killer=player)
                    self._pulse_hit_ids.add(p.id)
            if self._pulse_radius >= self.pulse_max_range:
                self._pulse_active = False
                self._pulse_hit_ids.clear()

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"]   = True
        d["place_range"]    = self.cast_range
        d["is_channeling"]  = self.is_channeling
        d["channel_timer"]  = round(self.channel_timer, 2)
        d["channel_time"]   = self.channel_time
        d["pulse_active"]   = self._pulse_active
        d["pulse_radius"]   = round(self._pulse_radius, 1)
        d["pulse_x"]        = round(self._pulse_x, 1)
        d["pulse_y"]        = round(self._pulse_y, 1)
        return d


#-------------------------------------------------------------------------------------------------------------------PlaceTurret
class PlaceTurret(AbilityBase):
    cooldown    = 15.0
    mana_cost   = 80
    max_turrets = 2
    place_range = 50

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

        player.mana -= self.mana_cost
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        self.activate(player, targets, target_pos, game_state)
        return True

    def activate(self, player, targets, target_pos=None, game_state=None):
        from server.entities import PlayerTurret
        tx, ty = target_pos
        tid = game_state._turret_counter[0]
        game_state._turret_counter[0] += 1
        game_state.player_turrets[tid] = PlayerTurret(tid, player.id, player.team, tx, ty)

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["max_turrets"]  = self.max_turrets
        d["place_range"]  = self.place_range
        return d


#-------------------------------------------------------------------------------------------------------------------Spin
class Spin(AbilityBase):
    cooldown      = 15.0
    mana_cost     = 80
    spin_duration = 5.0
    spin_radius   = 80
    tick_damage   = 25
    tick_interval = 0.5

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
        from server.projectiles import apply_damage
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
    cooldown    = 0.0
    mana_cost   = 0
    crit_chance = 0.25
    crit_mult   = 1.4

    def use(self, player, targets=None, target_pos=None, game_state=None):
        return False

    def to_dict(self):
        d = super().to_dict()
        d["is_passive"]  = True
        d["crit_chance"] = self.crit_chance
        d["crit_mult"]   = self.crit_mult
        return d


#-------------------------------------------------------------------------------------------------------------------Stealth
class Stealth(AbilityBase):
    cooldown    = 20.0
    mana_cost   = 60
    duration    = 12.0
    bonus_mult  = 1.5

    def __init__(self):
        super().__init__()
        self.is_active      = False
        self.duration_timer = 0.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        player.mana              -= self.mana_cost
        self.is_on_cooldown       = True
        self.cooldown_timer       = self.cooldown
        self.is_active            = True
        self.duration_timer       = self.duration
        player.is_invisible       = True
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
    cooldown    = 18.0
    mana_cost   = 50
    max_traps   = 3
    place_range = 200

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
        player.mana        -= self.mana_cost
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        from server.entities import Trap
        tid = game_state._trap_counter[0]
        game_state._trap_counter[0] += 1
        game_state.traps[tid] = Trap(tid, player.id, player.team, tx, ty)
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.place_range
        d["aoe_size"]     = 32
        return d


#-------------------------------------------------------------------------------------------------------------------Bolt
class Bolt(AbilityBase):
    cooldown   = 12.0
    mana_cost  = 70
    damage     = 280
    speed      = 175.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player):
            return False
        if target_pos is None or game_state is None:
            return False
        tx, ty = target_pos
        dx, dy = tx - player.x, ty - player.y
        if math.sqrt(dx * dx + dy * dy) < 1:
            return False
        player.mana        -= self.mana_cost
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        from server.projectiles import BoltProjectile
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
    cooldown     = 8.0
    mana_cost    = 0
    channel_time = 4.0

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
        from server.game_state import SPAWN_POSITIONS
        self.is_channeling  = False
        self.is_on_cooldown = True
        self.cooldown_timer = self.cooldown
        player.x, player.y  = SPAWN_POSITIONS.get(player.team, (60.0, 60.0))
        player.attack_target = None

    def to_dict(self):
        d = super().to_dict()
        d["is_channeling"]  = self.is_channeling
        d["channel_timer"]  = round(self.channel_timer, 2)
        d["channel_time"]   = self.channel_time
        d["is_recall"]      = True
        return d


#-------------------------------------------------------------------------------------------------------------------PlaceBanner
class PlaceBanner(AbilityBase):
    cooldown    = 30.0
    mana_cost   = 100
    place_range = 60

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
        from server.entities import Banner
        bid = game_state._banner_counter[0]
        game_state._banner_counter[0] += 1
        game_state.banners[bid] = Banner(bid, player.id, player.team, tx, ty)
        return True

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"] = True
        d["place_range"]  = self.place_range
        return d

