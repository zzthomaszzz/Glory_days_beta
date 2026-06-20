# Projectile classes and shared damage helpers (apply_damage, apply_on_hit_effects)
import math
import random

from shared.constants import RESPAWN_TIME, KILL_GOLD
from server.abilities import ABILITY_STATS


class Projectile:
    def __init__(self, proj_id, owner_id, owner_team, x, y, target_type, target_id, damage, armor, speed):
        self.proj_id     = proj_id
        self.owner_id    = owner_id
        self.owner_team  = owner_team
        self.x           = float(x)
        self.y           = float(y)
        self.target_type = target_type
        self.target_id   = int(target_id)
        self.damage      = damage
        self.armor       = armor
        self.speed       = speed
        self.is_done     = False

    def update(self, dt, players, buildings, player_turrets=None, banners=None):
        target = _resolve_target(self.target_type, self.target_id, players, buildings, player_turrets or {}, banners or {})
        if not target or getattr(target, "is_dead", False) or getattr(target, "is_destroyed", False):
            self.is_done = True
            return

        tx = getattr(target, 'cx', target.x)
        ty = getattr(target, 'cy', target.y)
        dx, dy = tx - self.x, ty - self.y
        dist   = math.sqrt(dx * dx + dy * dy)
        step   = self.speed * dt

        if dist <= step:
            killer = players.get(self.owner_id)
            apply_damage(target, self.damage, self.armor, killer=killer)
            if killer:
                apply_on_hit_effects(killer, target)
            _notify_auto_hit(target)
            self.is_done = True
        else:
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step

    def to_dict(self):
        return {
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "owner_team": self.owner_team,
        }


class FireballProjectile:
    SPEED = 350

    def __init__(self, proj_id, owner_team, x, y, target_x, target_y, tick_damage=20):
        self.proj_id     = proj_id
        self.owner_team  = owner_team
        self.x           = float(x)
        self.y           = float(y)
        self.target_x    = float(target_x)
        self.target_y    = float(target_y)
        self.tick_damage = tick_damage
        self.is_done     = False

    def update(self, dt, burning_areas, ba_counter):
        dx   = self.target_x - self.x
        dy   = self.target_y - self.y
        dist = math.sqrt(dx*dx + dy*dy)
        step = self.SPEED * dt
        if dist <= step:
            self.is_done = True
            from server.entities import BurningArea  # avoids circular import
            ba_id = ba_counter[0]
            ba_counter[0] += 1
            burning_areas[ba_id] = BurningArea(ba_id, self.target_x, self.target_y, self.owner_team, self.tick_damage)
        else:
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step

    def to_dict(self):
        return {
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "owner_team": self.owner_team,
            "is_fireball": True,
        }


class BoltProjectile:
    def __init__(self, proj_id, owner_id, owner_team, x, y, dx, dy, damage, speed):
        dist         = math.sqrt(dx * dx + dy * dy)
        self.proj_id     = proj_id
        self.owner_id    = owner_id
        self.owner_team  = owner_team
        self.x           = float(x)
        self.y           = float(y)
        self.vx          = (dx / dist) * speed
        self.vy          = (dy / dist) * speed
        self.damage      = damage
        self.angle       = math.degrees(math.atan2(-dy, dx))
        self.is_done     = False

    def update(self, dt, players):
        if self.is_done:
            return
        import pygame  # map_data imports pygame; deferred to keep server startup lean
        from shared.map_data import OBSTACLES
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        hit_box = pygame.Rect(int(nx - 4), int(ny - 4), 8, 8)
        if any(obs.colliderect(hit_box) for obs in OBSTACLES):
            self.is_done = True
            return
        self.x, self.y = nx, ny
        for p in players.values():
            if p.is_dead or p.team == self.owner_team:
                continue
            ddx = p.x - self.x
            ddy = p.y - self.y
            if ddx * ddx + ddy * ddy <= (p.size + 5) ** 2:
                apply_damage(p, self.damage, p.armor)
                self.is_done = True
                return

    def to_dict(self):
        return {
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "owner_team": self.owner_team,
            "angle":      round(self.angle, 1),
            "is_bolt":    True,
        }


class HookProjectile:
    _s         = ABILITY_STATS['Hook']
    SPEED      = _s['speed']
    MAX_RANGE  = _s['max_range']
    HIT_RADIUS = _s['hit_radius']
    PULL_DIST  = _s['pull_dist']
    DAMAGE     = _s['damage']
    STUN_DUR   = _s['stun_dur']

    def __init__(self, proj_id, owner_id, owner_team, x, y, dx, dy):
        dist            = math.sqrt(dx * dx + dy * dy) or 1
        self.proj_id    = proj_id
        self.owner_id   = owner_id
        self.owner_team = owner_team
        self.x          = float(x)
        self.y          = float(y)
        self.vx         = (dx / dist) * self.SPEED
        self.vy         = (dy / dist) * self.SPEED
        self.traveled   = 0.0
        self.is_done    = False

    def update(self, dt, players):
        if self.is_done:
            return
        import pygame  # map_data imports pygame; deferred to keep server startup lean
        from shared.map_data import OBSTACLES
        nx = self.x + self.vx * dt
        ny = self.y + self.vy * dt
        hit_box = pygame.Rect(int(nx - 4), int(ny - 4), 8, 8)
        if any(obs.colliderect(hit_box) for obs in OBSTACLES):
            self.is_done = True
            return
        self.x, self.y  = nx, ny
        self.traveled   += self.SPEED * dt
        if self.traveled >= self.MAX_RANGE:
            self.is_done = True
            return
        for p in players.values():
            if p.is_dead or p.team == self.owner_team:
                continue
            ddx = p.x - self.x
            ddy = p.y - self.y
            if ddx * ddx + ddy * ddy <= self.HIT_RADIUS ** 2:
                self._apply_hook(p, players)
                self.is_done = True
                return

    def _apply_hook(self, target, players):
        apply_damage(target, self.DAMAGE, target.armor)
        target.stun_timer = max(getattr(target, 'stun_timer', 0), self.STUN_DUR)
        owner = players.get(self.owner_id)
        if not owner or owner.is_dead:
            return
        dx   = owner.x - target.x
        dy   = owner.y - target.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist <= self.PULL_DIST:
            return
        ratio    = (dist - self.PULL_DIST) / dist
        target.x += dx * ratio
        target.y += dy * ratio

    def to_dict(self):
        return {
            "x":          round(self.x, 1),
            "y":          round(self.y, 1),
            "owner_id":   self.owner_id,
            "owner_team": self.owner_team,
        }


def _notify_auto_hit(target):
    for ab in getattr(target, 'abilities', []):
        if ab is not None and hasattr(ab, 'on_auto_hit'):
            ab.on_auto_hit(target)


def _resolve_target(target_type, target_id, players, buildings, player_turrets, banners):
    match target_type:
        case "player":   return players.get(target_id)
        case "building": return buildings.get(target_id)
        case "turret":   return player_turrets.get(target_id)
        case "banner":   return banners.get(target_id)
    return None


def apply_on_hit_effects(attacker, target):
    if not hasattr(target, 'armor_reduction_timer'):
        return
    if any(item == 'Fang' for item in getattr(attacker, 'inventory', [])):
        target.armor_reduction = 10
        target.armor_reduction_timer = 3.0


def apply_damage(target, raw_damage, armor, killer=None):
    effective_armor = max(0, armor - getattr(target, 'armor_reduction', 0))
    is_crit = False

    if killer is not None:
        for ab in getattr(killer, 'abilities', []):
            if ab is not None and hasattr(ab, 'crit_chance'):
                if random.random() < ab.crit_chance:
                    raw_damage = int(raw_damage * ab.crit_mult)
                    is_crit = True
                break

    damage = max(1, raw_damage - effective_armor)
    target.hp -= damage

    if is_crit and killer is not None:
        killer.hp = min(killer.max_hp, killer.hp + damage)

    if target.hp <= 0:
        target.hp = 0
        if hasattr(target, "is_destroyed"):
            target.is_destroyed = True
        elif hasattr(target, "is_dead"):
            target.is_dead = True
            target.respawn_timer = RESPAWN_TIME
            if killer is not None and getattr(killer, "team", None) != getattr(target, "team", None):
                killer.gold += KILL_GOLD
