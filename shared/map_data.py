# Static map layout: obstacle rects, bush zones, and capture-point spawn positions
import pygame

OBSTACLES = [
    pygame.Rect(256, 96, 32, 32),
    pygame.Rect(96, 288, 32, 32),
    pygame.Rect(128, 352, 64, 32),
    pygame.Rect(352, 192, 96, 32),
    pygame.Rect(480, 160, 96, 32),
    pygame.Rect(416, 224, 32, 64),
    pygame.Rect(448, 256, 32, 32),
    pygame.Rect(288, 448, 64, 32),
    pygame.Rect(672, 160, 64, 64),
    pygame.Rect(704, 320, 64, 32),
    pygame.Rect(736, 352, 32, 64),
    pygame.Rect(480, 352, 32, 32),
    pygame.Rect(544, 256, 32, 64),
    pygame.Rect(576, 256, 64, 32),
    pygame.Rect(608, 448, 32, 32),
    pygame.Rect(448, 544, 128, 32),
    pygame.Rect(608, 576, 64, 32),
    pygame.Rect(704, 512, 32, 64),
    pygame.Rect(704, 0, 64, 64),
    pygame.Rect(736, 64, 32, 32),
    pygame.Rect(448, 32, 96, 32),
    pygame.Rect(512, 64, 32, 64),
    pygame.Rect(192, 192, 64, 64),
    pygame.Rect(928, 544, 64, 32),
    pygame.Rect(832, 224, 64, 64),
    pygame.Rect(832, 416, 32, 64),
    pygame.Rect(992, 256, 96, 32),
    pygame.Rect(1056, 288, 32, 64),
    pygame.Rect(1024, 448, 64, 64),
    pygame.Rect(960, 672, 64, 32),
    pygame.Rect(1024, 640, 32, 32),
    pygame.Rect(1024, 160, 32, 64),
    pygame.Rect(864, 32, 96, 32),
    pygame.Rect(800, 96, 32, 64),
    pygame.Rect(1024, 64, 32, 32),
    pygame.Rect(352, 0, 32, 160),
    pygame.Rect(352, 640, 32, 64),
    pygame.Rect(576, 608, 32, 64),
    pygame.Rect(384, 736, 160, 32),
    pygame.Rect(32, 608, 64, 32),
    pygame.Rect(160, 640, 32, 64),
    pygame.Rect(1088, 96, 32, 32),
    pygame.Rect(1120, 160, 128, 32),
    pygame.Rect(1120, 384, 64, 32),
    pygame.Rect(1216, 416, 64, 32),
    pygame.Rect(0, 384, 64, 32),
    pygame.Rect(160, 448, 64, 64),
    pygame.Rect(672, 672, 96, 32),
    pygame.Rect(704, 480, 64, 32),
    pygame.Rect(928, 736, 32, 32),
    pygame.Rect(928, 672, 32, 32),
    pygame.Rect(896, 544, 32, 96),
    pygame.Rect(800, 640, 32, 128),
    pygame.Rect(800, 512, 32, 64),
    pygame.Rect(512, 416, 32, 64),
    pygame.Rect(448, 448, 32, 32),
]

# (x, y) top-left of each 32x32 capture point tile
CAPTURE_ZONES = [
    (320, 320),
    (608, 352),
    (480, 64),
    (928, 576),
    (960, 352),
    (896, 96),
    (448, 704),
    (96, 480),
    (1184, 256),
]

BUSHES = [
    pygame.Rect(160, 384, 64, 32),
    pygame.Rect(192, 352, 32, 32),
    pygame.Rect(256, 416, 64, 32),
    pygame.Rect(256, 448, 32, 32),
    pygame.Rect(384, 256, 32, 64),
    pygame.Rect(640, 448, 32, 32),
    pygame.Rect(640, 192, 32, 64),
    pygame.Rect(672, 224, 64, 32),
    pygame.Rect(608, 480, 64, 32),
    pygame.Rect(416, 288, 32, 32),
    pygame.Rect(416, 160, 64, 32),
    pygame.Rect(448, 192, 64, 32),
    pygame.Rect(480, 384, 64, 32),
    pygame.Rect(832, 384, 64, 32),
    pygame.Rect(864, 416, 32, 32),
    pygame.Rect(992, 416, 32, 64),
    pygame.Rect(1024, 416, 32, 32),
    pygame.Rect(704, 352, 32, 64),
    pygame.Rect(864, 192, 160, 32),
    pygame.Rect(1024, 96, 64, 64),
    pygame.Rect(448, 576, 32, 64),
    pygame.Rect(352, 608, 96, 32),
    pygame.Rect(320, 704, 64, 64),
    pygame.Rect(1184, 384, 64, 32),
    pygame.Rect(0, 416, 64, 32),
    pygame.Rect(160, 512, 32, 64),
    pygame.Rect(768, 672, 32, 64),
    pygame.Rect(960, 768, 32, 32),
    pygame.Rect(608, 608, 32, 32),
    pygame.Rect(832, 512, 96, 32),
    pygame.Rect(320, 480, 64, 32),
    pygame.Rect(480, 416, 32, 64),
]

# (team, x, y) — centre of each team's spawn point
SPAWN_POSITIONS = [
    (1, 224, 48),
    (2, 1040, 752),
]

# Derived rects for MapSystem fog-of-war node marking
SPAWN_ZONES = [pygame.Rect(x - 48, y - 48, 96, 96) for _, x, y in SPAWN_POSITIONS]


#Centre of each team's main base, aligned to spawn zones
BASE_POSITIONS = [
    (48, 48),    # team 0
    (1232, 752), # team 1
]

# (team, x, y) for each map Tower — top-left corner, size 32x32
# First entry per team becomes the shield tower (keeps that team's HQ invulnerable)
TOWER_POSITIONS = [
    (2, 1184, 672),
    (1, 64, 96),
]

# (team, x, y) — top-left corner of each HQ, size 48×48
HQ_POSITIONS = [
    (2, 1208, 728),
    (1, 24, 24),
]

# Water zones — players inside move at 50% speed
WATER_ZONES = [
    pygame.Rect(448, 288, 64, 64),
    pygame.Rect(608, 512, 96, 64),
    pygame.Rect(576, 160, 96, 32),
    pygame.Rect(640, 128, 96, 32),
    pygame.Rect(768, 384, 64, 64),
    pygame.Rect(896, 224, 128, 32),
    pygame.Rect(352, 544, 96, 64),
    pygame.Rect(800, 768, 160, 32),
]

# (team, x, y) — top-left corner of each shop building, size 32×32
SHOP_POSITIONS = [
    (1, 64, 704),
    (1, 1184, 64),
]
