import math

from shared.constants import MAP_W, MAP_H
from shared.map_data import OBSTACLES

_HALF = 16  # player is 32x32, center-based position


def apply_movement(players, dt):
    for player in players.values():
        if player.is_dead or player.is_attacking:
            continue
        if player.stun_timer > 0 or player.root_timer > 0:
            continue
        if any(getattr(ab, "is_channeling", False) for ab in player.abilities if ab):
            continue
        length = math.sqrt(player.dx ** 2 + player.dy ** 2)
        if length == 0:
            continue
        nx = player.dx / length
        ny = player.dy / length
        step = player.speed * player.slow_factor * dt

        player.x += nx * step
        player.x = max(_HALF, min(player.x, MAP_W - _HALF))
        _adjust_horizontal(player)

        player.y += ny * step
        player.y = max(_HALF, min(player.y, MAP_H - _HALF))
        _adjust_vertical(player)


def _adjust_horizontal(player):
    left   = player.x - _HALF
    right  = player.x + _HALF
    top    = player.y - _HALF
    bottom = player.y + _HALF
    for obs in OBSTACLES:
        if left < obs.right and right > obs.left and top < obs.bottom and bottom > obs.top:
            if obs.left < right < obs.right:
                player.x = obs.left - _HALF   # moving right, snap to left wall face
            elif obs.left < left < obs.right:
                player.x = obs.right + _HALF  # moving left, snap to right wall face
            break


def _adjust_vertical(player):
    left   = player.x - _HALF
    right  = player.x + _HALF
    top    = player.y - _HALF
    bottom = player.y + _HALF
    for obs in OBSTACLES:
        if left < obs.right and right > obs.left and top < obs.bottom and bottom > obs.top:
            if obs.top < bottom < obs.bottom:
                player.y = obs.top - _HALF     # moving down, snap to top wall face
            elif obs.top < top < obs.bottom:
                player.y = obs.bottom + _HALF  # moving up, snap to bottom wall face
            break
