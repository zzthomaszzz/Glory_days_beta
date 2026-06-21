# Static map layout: obstacle rects, bush zones, and capture-point spawn positions
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
    pygame.Rect(480, 256, 95, 63),   # extended +1 tile right  (15,8) 3×2
    pygame.Rect(512, 384, 31, 31),
    pygame.Rect(576, 320, 63, 31),
    pygame.Rect(512, 480, 63, 63),
    pygame.Rect(480, 672, 127, 31),
    pygame.Rect(512, 704, 31, 31),
    pygame.Rect(608, 608, 127, 31),
    pygame.Rect(672, 480, 31, 63),   # extended +2 tiles up    (21,13) 1×3
    pygame.Rect(768, 512, 127, 95),
    pygame.Rect(928, 576, 159, 63),  # extended +3 tiles right (29,18) 5×2
    pygame.Rect(1152, 448, 31, 63),
    pygame.Rect(832, 416, 31, 63),
    pygame.Rect(1024, 416, 63, 31),
    pygame.Rect(896, 320, 95, 63),
    pygame.Rect(1024, 352, 31, 63),
    pygame.Rect(704, 352, 31, 63),
    pygame.Rect(832, 288, 31, 31),
    pygame.Rect(768, 192, 31, 31),
    pygame.Rect(1024, 224, 63, 63),  # original right-side wall (32,7) 2×2
    pygame.Rect(928,  224, 63, 31),  # new: right flank choke  (29,7) 2×1
    pygame.Rect(608, 64, 95, 63),
    pygame.Rect(768, 64, 95, 63),
    pygame.Rect(1024, 96, 63, 63),
    pygame.Rect(1120, 640, 95, 31),  # new: bottom-right lower (35,20) 3×1
    pygame.Rect(864,  672, 63, 63),  # new: bottom-right fill  (27,21) 2×2
    pygame.Rect(160,  512, 63, 31),  # new: left flank wall    ( 5,16) 2×1
]

# (x, y) top-left of each 32x32 capture point tile
CAPTURE_ZONES = [
    (608, 384),   # dead centre        (19,12)
    (576,  32),   # top-centre         (18, 1)
    (608, 736),   # bottom-centre      (19,23)
    (224, 512),   # bottom-left flank  ( 7,16)
    (992, 256),   # top-right flank    (31, 8)
    ( 64, 288),   # top-left base area ( 2, 9)
    (1056, 384),  # right-side mid     (33,12)
]

BUSHES = [
    pygame.Rect( 96, 160, 31, 31),   # top-left area         ( 3, 5)
    pygame.Rect(448, 192, 31, 31),   # top mid-left          (14, 6)
    pygame.Rect(992, 160, 31, 31),   # top mid-right         (31, 5)
    pygame.Rect(544, 384, 31, 31),   # centre west of cap    (17,12)
    pygame.Rect(640, 480, 31, 31),   # centre east           (20,15)
    pygame.Rect(352, 448, 31, 31),   # centre west           (11,14)
    pygame.Rect(128, 544, 31, 31),   # left corridor         ( 4,17)
    pygame.Rect(448, 576, 31, 31),   # bottom mid-left       (14,18)
    pygame.Rect(800, 608, 31, 31),   # bottom mid-right      (25,19)
    pygame.Rect(1088, 512, 31, 31),  # right corridor        (34,16)
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

# (team, x, y) for each map Tower — top-left corner, size 32x32
# First entry per team becomes the shield tower (keeps that team's HQ invulnerable)
TOWER_POSITIONS = [
    # Team 1 — top-left base, HQ at (32, 32)
    (1, 160,  64),   # forward guard  [shield tower]
    # Team 2 — bottom-right base, HQ at (1200, 720)
    (2, 1088, 688),  # forward guard  [shield tower]
]
