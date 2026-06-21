# System: auto-attack targeting, windup timer, hit resolution, and stealth break
from shared.constants import ATTACK_WINDUP
from server.abilities import Stealth
from server.projectiles import Projectile, apply_damage, apply_on_hit_effects, _notify_auto_hit

_TURRET_REVEAL_DUR = 0.5   # seconds an invisible enemy stays revealed while in turret range
_BUSH_REVEAL_DUR   = 1.5   # seconds a player is revealed after attacking from a bush


def resolve_combat(players, buildings, player_turrets, banners, dt, projectiles, proj_counter, traps=None):
    for player in players.values():
        if player.is_dead:
            continue
        _tick_windup(player, dt, players, buildings, player_turrets, banners, traps=traps)
        _tick_attack(player, players, buildings, player_turrets, banners, dt, projectiles, proj_counter, traps=traps)


def resolve_turret_combat(player_turrets, players, dt, projectiles, proj_counter):
    for turret in player_turrets.values():
        if turret.is_destroyed:
            continue
        r2 = turret.attack_range ** 2
        for p in players.values():
            if p.is_dead or p.team == turret.team or not p.is_invisible:
                continue
            dx = p.x - turret.x
            dy = p.y - turret.y
            if dx * dx + dy * dy <= r2:
                p.revealed_timer = max(p.revealed_timer, _TURRET_REVEAL_DUR)
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

def _tick_windup(player, dt, players, buildings, player_turrets, banners, traps=None):
    """Pre-fire melee swing timer. Damage fires here when windup expires, not in _tick_attack."""
    if not player.is_attacking:
        return
    if player.is_dead:
        player.is_attacking    = False
        player._pending_damage = 0
        return
    player.attack_windup_timer -= dt
    if player.attack_windup_timer > 0:
        return
    # Windup complete — fire committed melee hit (no range re-check)
    player.is_attacking = False
    player.attack_timer = 1.0 / player.attack_speed
    if not player.attack_target:
        return
    target_type, target_id = player.attack_target
    target = _get_target(target_type, target_id, players, buildings, player_turrets, banners, traps=traps)
    if target and not _is_gone(target):
        apply_damage(target, player._pending_damage, target.armor, killer=player)
        apply_on_hit_effects(player, target)
        _notify_auto_hit(target)


def _tick_attack(player, players, buildings, player_turrets, banners, dt, projectiles, proj_counter, traps=None):
    if not player.attack_target:
        return

    target_type, target_id = player.attack_target
    target = _get_target(target_type, target_id, players, buildings, player_turrets, banners, traps=traps)

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

    # Enemy trap whose reveal has expired — deselect
    if target_type == "trap" and not getattr(target, "revealed_timer", 0) > 0:
        player.attack_target = None
        return

    # Skip if already in a melee windup (damage will fire from _tick_windup)
    if player.is_attacking:
        return

    # Count down between attacks; only check range when timer expires
    player.attack_timer -= dt
    if player.attack_timer > 0:
        return

    # Timer expired — check range before committing
    if not _in_range(player, target):
        player.attack_timer = 0.0   # stays primed; commits on next in-range tick
        return

    # Build damage value — capture stealth mult and break stealth at commit time
    damage = player.attack_damage
    if getattr(player, '_stealth_bonus_ready', False):
        stealth_ab = next((ab for ab in player.abilities if isinstance(ab, Stealth)), None)
        damage = int(damage * (stealth_ab.bonus_mult if stealth_ab else 1.5))
        player._stealth_bonus_ready = False
    _break_stealth(player)
    if player.bush_idx != -1:
        player.revealed_timer = max(player.revealed_timer, _BUSH_REVEAL_DUR)

    if player.is_ranged:
        # Ranged: projectile fires immediately; tracking makes it committed
        player.attack_timer = 1.0 / player.attack_speed
        _fire_projectile(player, target_type, int(target_id), target.armor, projectiles, proj_counter, damage)
    else:
        # Melee: commit to swing — damage fires after ATTACK_WINDUP in _tick_windup
        player._pending_damage     = damage
        player.is_attacking        = True
        player.attack_windup_timer = ATTACK_WINDUP
        # attack_timer stays at 0; _tick_windup resets it after damage fires


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

def _get_target(target_type, target_id, players, buildings, player_turrets, banners, traps=None):
    try:
        target_id = int(target_id)
    except (ValueError, TypeError):
        return None
    match target_type:
        case "player":   return players.get(target_id)
        case "building": return buildings.get(target_id)
        case "turret":   return player_turrets.get(target_id)
        case "banner":   return banners.get(target_id)
        case "trap":     return (traps or {}).get(target_id)
    return None


def _is_gone(target):
    return getattr(target, "is_dead", False) or getattr(target, "is_destroyed", False)


def _in_range(attacker, target):
    dx = attacker.x - target.x
    dy = attacker.y - target.y
    return dx*dx + dy*dy <= attacker.attack_range ** 2
