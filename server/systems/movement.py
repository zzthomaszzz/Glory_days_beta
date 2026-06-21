# System: applies player velocity, enforces map bounds and obstacle collision
import math
import pygame

from shared.constants import MAP_W, MAP_H
from shared.map_data import OBSTACLES, WATER_ZONES

_HALF        = 16   # player is 32x32, center-based position
_SKIP_BLDG   = {'Banner', 'CapturePoint'}   # pass-through: Banner (temp flag), CapturePoint (must stand on to capture)


def apply_pull(players, dt):
    for player in players.values():
        if player.pull_timer <= 0:
            continue
        player.pull_timer -= dt
        player.x = max(_HALF, min(player.x + player.pull_vx * dt, MAP_W - _HALF))
        player.y = max(_HALF, min(player.y + player.pull_vy * dt, MAP_H - _HALF))
        if player.pull_timer <= 0:
            player.pull_vx = 0.0
            player.pull_vy = 0.0


def _build_obs_list(collidables):
    obs = list(OBSTACLES)
    if collidables:
        for b in collidables:
            if getattr(b, 'is_destroyed', False):
                continue
            if type(b).__name__ in _SKIP_BLDG:
                continue
            obs.append(pygame.Rect(b.x, b.y, b.size, b.size))
    return obs


def apply_movement(players, dt, collidables=None):
    obs_list = _build_obs_list(collidables)
    for player in players.values():
        if player.is_dead or player.is_attacking:   # is_attacking = True during pre-fire melee windup
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
        water_slow = 0.5 if any(z.collidepoint(player.x, player.y) for z in WATER_ZONES) else 1.0
        step = player.speed * player.slow_factor * water_slow * dt

        player.x += nx * step
        player.x = max(_HALF, min(player.x, MAP_W - _HALF))
        _adjust_horizontal(player, obs_list)

        player.y += ny * step
        player.y = max(_HALF, min(player.y, MAP_H - _HALF))
        _adjust_vertical(player, obs_list)


def _adjust_horizontal(player, obs_list):
    for _ in range(8):
        left   = player.x - _HALF
        right  = player.x + _HALF
        top    = player.y - _HALF
        bottom = player.y + _HALF
        for obs in obs_list:
            if left < obs.right and right > obs.left and top < obs.bottom and bottom > obs.top:
                if obs.left < right < obs.right:
                    player.x = obs.left - _HALF
                elif obs.left < left < obs.right:
                    player.x = obs.right + _HALF
                break  # snap done — recalculate bounds and check again
        else:
            return  # full scan found no collision — done


def _adjust_vertical(player, obs_list):
    for _ in range(8):
        left   = player.x - _HALF
        right  = player.x + _HALF
        top    = player.y - _HALF
        bottom = player.y + _HALF
        for obs in obs_list:
            if left < obs.right and right > obs.left and top < obs.bottom and bottom > obs.top:
                if obs.top < bottom < obs.bottom:
                    player.y = obs.top - _HALF
                elif obs.top < top < obs.bottom:
                    player.y = obs.bottom + _HALF
                break  # snap done — recalculate bounds and check again
        else:
            return  # full scan found no collision — done
