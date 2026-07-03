"""Central constants. Gameplay feel and audio geometry live here (ADR 0001, 0004)."""

# --- audio geometry (ADR 0002) ---
SAMPLE_RATE: int = 48000
BLOCKSIZE: int = 256  # samples per hop; 5.333 ms at 48 kHz

# --- display ---
SCREEN_W: int = 800
SCREEN_H: int = 400
FPS: int = 60
GROUND_Y: int = 310

# --- colours ---
WHITE: tuple[int, int, int] = (255, 255, 255)
BLACK: tuple[int, int, int] = (30, 30, 30)
GREY: tuple[int, int, int] = (83, 83, 83)
DARK: tuple[int, int, int] = (50, 50, 50)

# --- gameplay geometry ---
DINO_X: int = 80  # fixed dino x-position; obstacles arrive here on beats
PX_PER_SEC: float = 360.0  # obstacle scroll speed (time-derived motion, ADR 0004)

# --- jump physics: AIR TIME is the design constant (ADR 0004) ---
# Jumps must fit inside a beat period. JUMP_VEL/GRAVITY are DERIVED:
#   t_air = 2*v0/g  and  h = v0^2/(2g)   =>   v0 = 4h/t_air,  g = 2*v0/t_air
AIR_TIME_S: float = 0.35
JUMP_HEIGHT_PX: float = 90.0
_AIR_FRAMES: float = AIR_TIME_S * FPS
JUMP_VEL: float = -4.0 * JUMP_HEIGHT_PX / _AIR_FRAMES  # px/frame, negative = up
GRAVITY: float = -2.0 * JUMP_VEL / _AIR_FRAMES  # px/frame^2, positive = down
