# System: auto-attack targeting, windup timer, hit resolution, and stealth break
from shared.constants import ATTACK_WINDUP
from server.abilities import Stealth
from server.projectiles import Projectile, apply_damage, apply_on_hit_effects, _notify_auto_hit


def resolve_combat(players, buildings, player_turrets, banners, dt, projectiles, proj_counter):
    for player in players.values():
        if player.is_dead:
            continue
        _tick_windup(player, dt)
        _tick_attack(player, players, buildings, player_turrets, banners, dt, projectiles, proj_counter)


def resolve_turret_combat(player_turrets, players, dt, projectiles, proj_counter):
    for turret in player_turrets.values():
        if turret.is_destroyed:
            continue
        turret.attack_timer -= dt
        if turret.attack_timer > 0:
            continue
        target = _find_turret_target(turret, players)
        if not target:
            continue
        turret.attack_timer = 1.0 / turret.attack_speed
        pid = proj_counter[0]
        proj_counter[0] += 1
        projectiles[pid] = Projectile(
            pid, turret.id, turret.team,
            turret.x, turret.y,
            "player", target.id,
            turret.attack_damage, target.armor,
            turret.proj_speed,
        )


# ---------------------------------------------------------------------------
# Player attack helpers
# ---------------------------------------------------------------------------

def _tick_windup(player, dt):
    """Count down the visual attack-swing state set when an attack fires."""
    if player.is_attacking:
        player.attack_windup_timer -= dt
        if player.attack_windup_timer <= 0:
            player.is_attacking = False


def _tick_attack(player, players, buildings, player_turrets, banners, dt, projectiles, proj_counter):
    if not player.attack_target:
        return

    target_type, target_id = player.attack_target
    target = _get_target(target_type, target_id, players, buildings, player_turrets, banners)

    # Target gone — stop attacking
    if not target or _is_gone(target):
        player.attack_target = None
        return

    # Target is neutral (team 0) or friendly — deselect
    target_team = getattr(target, "team", None)
    if target_team == 0 or target_team == player.team:
        player.attack_target = None
        return

    # Invisible and not revealed — players cannot see stealthed enemies
    if getattr(target, "is_invisible", False) and not getattr(target, "revealed_timer", 0) > 0:
        player.attack_target = None
        return

    # Out of range — hold target but don't tick the timer
    if not _in_range(player, target):
        return

    # Count down between attacks
    player.attack_timer -= dt
    if player.attack_timer > 0:
        return

    # Fire — reset timer but keep target so the next swing happens automatically
    player.attack_timer = 1.0 / player.attack_speed
    player.is_attacking = True
    player.attack_windup_timer = ATTACK_WINDUP

    damage = player.attack_damage
    if getattr(player, '_stealth_bonus_ready', False):
        stealth_ab = next((ab for ab in player.abilities if isinstance(ab, Stealth)), None)
        damage = int(damage * (stealth_ab.bonus_mult if stealth_ab else 1.5))
        player._stealth_bonus_ready = False
    _break_stealth(player)

    if player.is_ranged:
        _fire_projectile(player, target_type, int(target_id), target.armor, projectiles, proj_counter, damage)
    else:
        apply_damage(target, damage, target.armor, killer=player)
        apply_on_hit_effects(player, target)
        _notify_auto_hit(target)


def _fire_projectile(player, target_type, target_id, target_armor, projectiles, proj_counter, damage=None):
    pid = proj_counter[0]
    proj_counter[0] += 1
    projectiles[pid] = Projectile(
        pid, player.id, player.team,
        player.x, player.y,
        target_type, target_id,
        damage if damage is not None else player.attack_damage,
        target_armor,
        player.proj_speed,
    )


def _break_stealth(player):
    if not player.is_invisible:
        return
    player.is_invisible = False
    for ab in player.abilities:
        if ab and getattr(ab, 'is_active', False) and isinstance(ab, Stealth):
            ab.is_active      = False
            ab.duration_timer = 0.0


# ---------------------------------------------------------------------------
# Turret helpers
# ---------------------------------------------------------------------------

def _find_turret_target(turret, players):
    # Turrets have true sight — they can detect invisible (stealthed) enemies
    best    = None
    best_d2 = turret.attack_range ** 2
    for p in players.values():
        if p.is_dead or p.team == turret.team:
            continue
        dx = p.x - turret.x
        dy = p.y - turret.y
        d2 = dx*dx + dy*dy
        if d2 <= best_d2:
            best_d2 = d2
            best    = p
    return best


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _get_target(target_type, target_id, players, buildings, player_turrets, banners):
    match target_type:
        case "player":   return players.get(int(target_id))
        case "building": return buildings.get(int(target_id))
        case "turret":   return player_turrets.get(int(target_id))
        case "banner":   return banners.get(int(target_id))
    return None


def _is_gone(target):
    return getattr(target, "is_dead", False) or getattr(target, "is_destroyed", False)


def _in_range(attacker, target):
    dx = attacker.x - target.x
    dy = attacker.y - target.y
    return dx*dx + dy*dy <= attacker.attack_range ** 2
