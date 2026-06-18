import pygame

OBSTACLES = [
    pygame.Rect(224, 288, 63, 63),
    pygame.Rect(128, 352, 63, 63),
    pygame.Rect(256, 704, 31, 31),
    pygame.Rect(256, 576, 63, 63),
    pygame.Rect(896, 0, 31, 63),
    pygame.Rect(352, 192, 63, 63),
    pygame.Rect(512, 160, 95, 63),
    pygame.Rect(32, 256, 127, 31),
    pygame.Rect(32, 288, 31, 63),
    pygame.Rect(256, 448, 31, 127),
    pygame.Rect(288, 96, 63, 63),
    pygame.Rect(384, 320, 31, 63),
    pygame.Rect(288, 640, 127, 31),
    pygame.Rect(384, 544, 63, 31),
    pygame.Rect(320, 736, 95, 63),
    pygame.Rect(480, 256, 63, 63),
    pygame.Rect(512, 384, 31, 31),
    pygame.Rect(576, 320, 63, 31),
    pygame.Rect(512, 480, 63, 63),
    pygame.Rect(480, 672, 127, 31),
    pygame.Rect(512, 704, 31, 31),
    pygame.Rect(608, 608, 127, 31),
    pygame.Rect(672, 480, 31, 31),
    pygame.Rect(768, 512, 127, 95),
    pygame.Rect(928, 576, 63, 63),
    pygame.Rect(1152, 448, 31, 63),
    pygame.Rect(832, 416, 31, 63),
    pygame.Rect(1024, 416, 63, 31),
    pygame.Rect(896, 320, 95, 63),
    pygame.Rect(1024, 352, 31, 63),
    pygame.Rect(704, 352, 31, 63),
    pygame.Rect(832, 288, 31, 31),
    pygame.Rect(768, 192, 31, 31),
    pygame.Rect(1024, 224, 63, 63),
    pygame.Rect(608, 64, 95, 63),
    pygame.Rect(768, 64, 95, 63),
    pygame.Rect(1024, 96, 63, 63),
]

HEAL_ZONES = [
    pygame.Rect(64, 288, 31, 31),
    pygame.Rect(608, 736, 31, 31),
    pygame.Rect(1056, 384, 31, 31),
    pygame.Rect(576, 32, 31, 31),
]

# (x, y) top-left of each 32x32 capture point tile
CAPTURE_ZONES = [
    (64,   288),   # top-left quadrant
    (608,  736),   # bottom-centre
    (1056, 384),   # right side
    (576,  32),    # top-centre
    (624,  384),   # dead centre
    (432,  416),   # centre-left flank
    (768,  368),   # centre-right flank
]

SPAWN_ZONES = [
    pygame.Rect(0, 0, 96, 96),       # team 0 (top-left)
    pygame.Rect(1184, 704, 96, 96),  # team 1 (bottom-right)
]


#Centre of each team's main base, aligned to spawn zones
BASE_POSITIONS = [
    (48, 48),    # team 0
    (1232, 752), # team 1
]
