#Network
CLIENT_INPUT_INTERVAL = 0.025
SNAPSHOT_INTERVAL = 0.05
SERVER_PORT = 5555
SERVER_HOST = "0.0.0.0"

#Client
FPS = 120

#Map
NODE_SIZE = 16
MAP_W = 1280
MAP_H = 800

#Economy
MINERAL_START         = 240    # HQ pool — 120 ticks × 5s = 10-minute lifespan
CAPTURE_MINERAL_START = 100    # capture point pool — 50 ticks × 5s ≈ 4 minutes
GOLD_PER_MINERAL      = 1
MINERALS_PER_TICK     = 2
GOLD_TICK_INTERVAL    = 5.0

#Combat
RESPAWN_TIME = 9.0
KILL_GOLD    = 25
ATTACK_WINDUP = 0.25

#Building
BUILDING_SIZE = 48

#Vision (world pixels, per building type)
BASE_VISION = 150
TURRET_VISION = 150

#Attrition rune
RUNE_X            = 640    # world center
RUNE_Y            = 400
RUNE_RADIUS       = 32
RUNE_CAPTURE_TIME = 5.0
RUNE_RESPAWN_TIME = 60.0
RUNE_DAMAGE       = 200

#Capture points
CAPTURE_TIME   = 5.0   # seconds standing on point to capture
CAPTURE_RADIUS = 48    # px from point centre that counts as "standing on"
CAPTURE_SIZE   = 32    # building tile size
CAPTURE_VISION = 75   # fog vision radius
CAPTURE_HP     = 300   # HP before the point resets to neutral
