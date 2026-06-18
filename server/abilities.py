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

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        from server.projectiles import apply_damage
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
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

    def to_dict(self):
        d = super().to_dict()
        d["slam_radius"] = self.slam_radius
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
    cooldown     = 18.0
    mana_cost    = 80
    channel_time = 1.5
    cast_range   = 450

    def __init__(self):
        super().__init__()
        self.is_channeling  = False
        self.channel_timer  = 0.0
        self.target_pos     = None
        self._hp_snapshot   = 0.0

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
        if not self.is_channeling:
            return
        if player.hp < self._hp_snapshot:
            # damaged — cancel channel, keep cooldown
            self.is_channeling = False
            self.target_pos    = None
            return
        self.channel_timer -= dt
        if self.channel_timer <= 0:
            self.is_channeling = False
            if self.target_pos:
                player.x, player.y = self.target_pos
            self.target_pos = None

    def to_dict(self):
        d = super().to_dict()
        d["is_placement"]  = True
        d["place_range"]   = self.cast_range
        d["is_channeling"] = self.is_channeling
        d["channel_timer"] = round(self.channel_timer, 2)
        d["channel_time"]  = self.channel_time
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


#-------------------------------------------------------------------------------------------------------------------Blitz
class Blitz(AbilityBase):
    cooldown   = 7.0
    mana_cost  = 60
    cast_range = 220
    damage     = 35

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
        self._blitz(player, target)
        return True

    def _blitz(self, player, target):
        import pygame
        from shared.map_data import OBSTACLES
        from server.projectiles import apply_damage
        dx, dy    = target.x - player.x, target.y - player.y
        dist      = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        ux, uy    = dx / dist, dy / dist
        stop_dist = max(0, dist - player.size)
        half      = player.size // 2
        nx, ny    = player.x, player.y
        for _ in range(max(1, int(stop_dist))):
            tx2 = nx + ux
            ty2 = ny + uy
            pr  = pygame.Rect(int(tx2 - half), int(ty2 - half), player.size, player.size)
            if any(obs.colliderect(pr) for obs in OBSTACLES):
                break
            nx, ny = tx2, ty2
        player.x, player.y = nx, ny
        apply_damage(target, self.damage, target.armor, killer=player)

    def to_dict(self):
        d = super().to_dict()
        d["is_targeted"] = True
        d["cast_range"]  = self.cast_range
        return d


#-------------------------------------------------------------------------------------------------------------------Whirlwind
class Whirlwind(AbilityBase):
    cooldown  = 9.0
    mana_cost = 70
    radius    = 90
    damage    = 70

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        from server.projectiles import apply_damage
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        r2 = self.radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team == player.team:
                continue
            dx, dy = p.x - player.x, p.y - player.y
            if dx * dx + dy * dy <= r2:
                apply_damage(p, self.damage, p.armor, killer=player)
        return True

    def to_dict(self):
        d = super().to_dict()
        d["slam_radius"] = self.radius
        return d


#-------------------------------------------------------------------------------------------------------------------Adrenaline
class Adrenaline(AbilityBase):
    cooldown      = 14.0
    mana_cost     = 50
    atk_spd_bonus = 0.6
    duration      = 4.0

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
        player.attack_speed += self.atk_spd_bonus
        return True

    def tick(self, dt, player, game_state):
        if not self.is_active:
            return
        self.duration_timer -= dt
        if self.duration_timer <= 0:
            self.is_active       = False
            self.duration_timer  = 0.0
            player.attack_speed -= self.atk_spd_bonus

    def to_dict(self):
        d = super().to_dict()
        d["is_active"]      = self.is_active
        d["duration_timer"] = round(self.duration_timer, 2)
        d["duration"]       = self.duration
        return d


#-------------------------------------------------------------------------------------------------------------------ShieldBash
class ShieldBash(AbilityBase):
    cooldown      = 8.0
    mana_cost     = 55
    radius        = 80
    damage        = 30
    slow_factor   = 0.5
    slow_duration = 2.0

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        from server.projectiles import apply_damage
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        r2 = self.radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team == player.team:
                continue
            dx, dy = p.x - player.x, p.y - player.y
            if dx * dx + dy * dy <= r2:
                apply_damage(p, self.damage, p.armor, killer=player)
                p.slow_timer  = self.slow_duration
                p.slow_factor = self.slow_factor
        return True

    def to_dict(self):
        d = super().to_dict()
        d["slam_radius"] = self.radius
        return d


#-------------------------------------------------------------------------------------------------------------------IronWall
class IronWall(AbilityBase):
    cooldown    = 16.0
    mana_cost   = 70
    armor_bonus = 50
    mr_bonus    = 40
    duration    = 3.5

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


#-------------------------------------------------------------------------------------------------------------------Warcry
class Warcry(AbilityBase):
    cooldown  = 20.0
    mana_cost = 80
    radius    = 110
    stun_dur  = 1.2

    def use(self, player, targets=None, target_pos=None, game_state=None):
        if not self.can_use(player) or game_state is None:
            return False
        player.mana         -= self.mana_cost
        self.is_on_cooldown  = True
        self.cooldown_timer  = self.cooldown
        r2 = self.radius ** 2
        for p in game_state.players.values():
            if p.is_dead or p.team == player.team:
                continue
            dx, dy = p.x - player.x, p.y - player.y
            if dx * dx + dy * dy <= r2:
                p.stun_timer = self.stun_dur
        return True

    def to_dict(self):
        d = super().to_dict()
        d["slam_radius"] = self.radius
        return d
