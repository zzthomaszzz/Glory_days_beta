from shared.constants import ATTACK_WINDUP
from server.projectiles import Projectile, apply_damage, apply_on_hit_effects


def resolve_combat(players, buildings, player_turrets, dt, projectiles, proj_counter):
    for player in players.values():
        if player.is_dead:
            continue

        if player.is_attacking:
            player.attack_windup_timer -= dt
            if player.attack_windup_timer <= 0:
                player.is_attacking = False

        if not player.attack_target:
            continue

        target_type, target_id = player.attack_target
        target = _get_target(target_type, target_id, players, buildings, player_turrets)

        if not target or _is_gone(target):
            player.attack_target = None
            continue

        target_team = getattr(target, "team", None)
        if target_team == 0 or target_team == player.team:
            player.attack_target = None
            continue

        if not _in_range(player, target):
            continue

        player.attack_timer -= dt
        if player.attack_timer <= 0:
            player.attack_timer        = 1.0 / player.attack_speed
            player.is_attacking        = True
            player.attack_windup_timer = ATTACK_WINDUP
            player.attack_target       = None

            if player.is_ranged:
                pid = proj_counter[0]
                proj_counter[0] += 1
                projectiles[pid] = Projectile(
                    pid, player.id, player.team,
                    player.x, player.y,
                    target_type, int(target_id),
                    player.attack_damage, target.armor,
                    player.proj_speed,
                )
            else:
                apply_damage(target, player.attack_damage, target.armor, killer=player)
                apply_on_hit_effects(player, target)


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


def update_projectiles(projectiles, players, buildings, player_turrets, dt):
    for proj in list(projectiles.values()):
        proj.update(dt, players, buildings, player_turrets)
    for k in [k for k, p in projectiles.items() if p.is_done]:
        del projectiles[k]


def _find_turret_target(turret, players):
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


def _get_target(target_type, target_id, players, buildings, player_turrets):
    match target_type:
        case "player":   return players.get(int(target_id))
        case "building": return buildings.get(int(target_id))
        case "turret":   return player_turrets.get(int(target_id))
    return None


def _is_gone(target):
    return getattr(target, "is_dead", False) or getattr(target, "is_destroyed", False)


def _in_range(attacker, target):
    dx = attacker.x - target.x
    dy = attacker.y - target.y
    return dx*dx + dy*dy <= attacker.attack_range ** 2
