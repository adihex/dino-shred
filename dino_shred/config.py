"""Central constants. Gameplay feel and audio geometry live here (ADR 0001, 0004)."""

# --- audio geometry (ADR 0002) ---
SAMPLE_RATE = 48000
BLOCKSIZE = 256  # samples per hop; 5.333 ms at 48 kHz

# --- display ---
SCREEN_W = 800
SCREEN_H = 400
FPS = 60
GROUND_Y = 310

# --- colours ---
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
GREY = (83, 83, 83)
DARK = (50, 50, 50)

# --- gameplay geometry ---
DINO_X = 80  # fixed dino x-position; obstacles arrive here on beats
PX_PER_SEC = 360.0  # obstacle scroll speed (time-derived motion, ADR 0004)

# --- jump physics: AIR TIME is the design constant (ADR 0004) ---
# Jumps must fit inside a beat period. JUMP_VEL/GRAVITY are DERIVED:
#   t_air = 2*v0/g  and  h = v0^2/(2g)   =>   v0 = 4h/t_air,  g = 2*v0/t_air
AIR_TIME_S = 0.35
JUMP_HEIGHT_PX = 90.0
_AIR_FRAMES = AIR_TIME_S * FPS
JUMP_VEL = -4.0 * JUMP_HEIGHT_PX / _AIR_FRAMES  # px/frame, negative = up
GRAVITY = -2.0 * JUMP_VEL / _AIR_FRAMES  # px/frame^2
