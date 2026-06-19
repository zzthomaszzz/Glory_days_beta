from shared.map_data import BUSHES


def tick_player_status(players, dt):
    for player in players.values():
        if player.is_dead:
            continue
        if player.hp_regen > 0:
            player.hp = min(player.max_hp, player.hp + player.hp_regen * dt)
        if player.stun_timer > 0:
            player.stun_timer = max(0.0, player.stun_timer - dt)
        if player.slow_timer > 0:
            player.slow_timer = max(0.0, player.slow_timer - dt)
            if player.slow_timer <= 0:
                player.slow_factor = 1.0
        if player.root_timer > 0:
            player.root_timer = max(0.0, player.root_timer - dt)
        if player.bleed_timer > 0:
            from server.projectiles import apply_damage
            apply_damage(player, player.bleed_dps * dt, 0)
            player.bleed_timer = max(0.0, player.bleed_timer - dt)
            if player.bleed_timer <= 0:
                player.bleed_dps = 0.0
        if player.revealed_timer > 0:
            player.revealed_timer = max(0.0, player.revealed_timer - dt)
        if player.armor_reduction_timer > 0:
            player.armor_reduction_timer = max(0.0, player.armor_reduction_timer - dt)
            if player.armor_reduction_timer <= 0:
                player.armor_reduction = 0

        player.bush_idx = -1
        for i, bush in enumerate(BUSHES):
            if bush.collidepoint(int(player.x), int(player.y)):
                player.bush_idx = i
                break
