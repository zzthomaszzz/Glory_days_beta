import random

from shared.constants import RUNE_X, RUNE_Y, RUNE_RADIUS, RUNE_CAPTURE_TIME, RUNE_RESPAWN_TIME, RUNE_DAMAGE


def update_rune(rune, players, minerals_exhausted, dt):
    if not minerals_exhausted:
        rune["state"] = "inactive"
        return

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
        for player in players.values():
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
                _trigger_rune(rune, players, team)


def _trigger_rune(rune, players, capturing_team):
    from server.projectiles import apply_damage
    enemy_team    = 2 if capturing_team == 1 else 1
    alive_enemies = [p for p in players.values() if p.team == enemy_team and not p.is_dead]
    if alive_enemies:
        apply_damage(random.choice(alive_enemies), RUNE_DAMAGE, 0)
    rune["state"]         = "cooldown"
    rune["respawn_timer"] = RUNE_RESPAWN_TIME
    rune["capture_timer"] = 0.0
    rune["capturer_team"] = None
