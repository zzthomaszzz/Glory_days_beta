def update_effects(projectiles, fireball_projectiles, burning_areas, banners,
                   players, buildings, player_turrets, ba_counter, dt):
    _tick_projectiles(projectiles, players, buildings, player_turrets, banners, dt)
    _tick_fireballs(fireball_projectiles, burning_areas, ba_counter, dt)
    _tick_burning_areas(burning_areas, players, player_turrets, dt)
    _tick_banners(banners, players, dt)


def _tick_projectiles(projectiles, players, buildings, player_turrets, banners, dt):
    for proj in list(projectiles.values()):
        proj.update(dt, players, buildings, player_turrets, banners)
    for k in [k for k, p in projectiles.items() if p.is_done]:
        del projectiles[k]


def _tick_fireballs(fireball_projectiles, burning_areas, ba_counter, dt):
    for fp in list(fireball_projectiles.values()):
        fp.update(dt, burning_areas, ba_counter)
    for k in [k for k, fp in fireball_projectiles.items() if fp.is_done]:
        del fireball_projectiles[k]


def _tick_burning_areas(burning_areas, players, player_turrets, dt):
    for ba in list(burning_areas.values()):
        ba.update(dt, players, player_turrets)
    for k in [k for k, ba in burning_areas.items() if ba.is_expired]:
        del burning_areas[k]


def _tick_banners(banners, players, dt):
    for banner in list(banners.values()):
        banner.update(dt, players)
    for k in [k for k, b in banners.items() if b.is_destroyed]:
        del banners[k]
