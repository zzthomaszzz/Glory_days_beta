import math
import random

from shared.constants import RESPAWN_TIME, KILL_GOLD


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

        tx, ty = target.x, target.y
        dx, dy = tx - self.x, ty - self.y
        dist   = math.sqrt(dx * dx + dy * dy)
        step   = self.speed * dt

        if dist <= step:
            killer = players.get(self.owner_id)
            apply_damage(target, self.damage, self.armor, killer=killer)
            if killer:
                apply_on_hit_effects(killer, target)
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
            from server.entities import BurningArea
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
    if any(item and item.get('name') == 'Fang' for item in getattr(attacker, 'inventory', [])):
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
