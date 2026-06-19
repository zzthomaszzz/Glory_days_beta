# shared/protocol.py

# --- Client -> Server ---

def make_input_message(dx, dy, attack=None, ability=None, ability_target=None, ability_target_id=None):
    msg = {"type": "input", "dx": dx, "dy": dy}
    if attack:
        msg["target_type"] = attack[0]
        msg["target_id"]   = attack[1]
    if ability is not None:
        msg["ability"] = ability
    if ability_target:
        msg["ability_target_x"] = ability_target[0]
        msg["ability_target_y"] = ability_target[1]
    if ability_target_id is not None:
        msg["ability_target_id"] = ability_target_id
    return msg


def make_hero_select_message(hero_name):
    return {"type": "hero_select", "hero": hero_name}


# --- Server -> Client ---

def make_snapshot(match_time, players, buildings, projectiles=None, player_turrets=None,
                  fireball_projectiles=None, burning_areas=None, banners=None, shops=None,
                  winner=None, events=None, game_phase="live", countdown_timer=0.0,
                  ready_players=None, wait_elapsed=0.0, minerals_exhausted=False, rune=None):
    targeted_ids  = set()
    ready_set     = set(ready_players) if ready_players else set()
    for p in players.values():
        for ab in p.abilities:
            if ab and getattr(ab, "is_channeling", False) and getattr(ab, "target_id", None) is not None:
                targeted_ids.add(ab.target_id)

    player_dicts = {}
    for pid, p in players.items():
        d = p.to_dict()
        d["is_targeted"] = int(pid) in targeted_ids
        d["is_ready"]    = int(pid) in ready_set
        player_dicts[str(pid)] = d

    return {
        "type":        "snapshot",
        "match_time":  match_time,
        "game_phase":          game_phase,
        "countdown_timer":     round(countdown_timer, 1),
        "wait_elapsed":        round(wait_elapsed, 0),
        "minerals_exhausted":  minerals_exhausted,
        "players":     player_dicts,
        "buildings":   {str(bid): b.to_dict() for bid, b in buildings.items()},
        "projectiles":          {str(k): p.to_dict() for k, p in (projectiles or {}).items()},
        "fireball_projectiles": {str(k): p.to_dict() for k, p in (fireball_projectiles or {}).items()},
        "turrets":              {str(k): t.to_dict() for k, t in (player_turrets or {}).items()},
        "burning_areas":        {str(k): b.to_dict() for k, b in (burning_areas or {}).items()},
        "banners":              {str(k): b.to_dict() for k, b in (banners or {}).items()},
        "shops":                {str(k): s.to_dict() for k, s in (shops or {}).items()},
        "winner":      winner,
        "events":      events or [],
        "rune":        {
            "state":         (rune or {}).get("state", "inactive"),
            "capture_timer": round((rune or {}).get("capture_timer", 0.0), 2),
            "capturer_team": (rune or {}).get("capturer_team"),
            "respawn_timer": round((rune or {}).get("respawn_timer", 0.0), 1),
        },
    }
