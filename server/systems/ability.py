def update_abilities(players, dt, game_state=None):
    for player in players.values():
        for ability in player.abilities:
            if ability:
                ability.update(dt)
                if game_state and hasattr(ability, "tick"):
                    ability.tick(dt, player, game_state)
