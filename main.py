"""
Chrome Dino Runner — a pygame tutorial
=======================================
Core concepts covered:
  1. Game loop (INPUT → UPDATE → RENDER)
  2. State machine (START / PLAYING / GAME_OVER)
  3. Input abstraction (actions, not raw keys)
  4. AABB collision detection
  5. Object pooling (reusing obstacle list)
  6. Progressive difficulty
"""

import random
import sys

import pygame

# ---------------------------------------------------------------------------
# 1. CONSTANTS — tweak these to change feel
# ---------------------------------------------------------------------------
SCREEN_W = 800
SCREEN_H = 400
FPS = 60

# Colours (R, G, B)
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
GREY = (83, 83, 83)
DARK = (50, 50, 50)

GROUND_Y = 310  # where the ground line sits
GRAVITY = 0.8  # pixels/frame²
JUMP_VEL = -14.0  # initial upward velocity (negative = up)

BASE_SPEED = 6.0  # starting obstacle scroll speed
MAX_SPEED = 14.0  # cap on speed
SPEED_UP_PER_POINT = 0.01  # speed increase per score point

OBSTACLE_SPAWN_MIN = 50  # min frames between spawns
OBSTACLE_SPAWN_MAX = 120  # max frames between spawns

# ---------------------------------------------------------------------------
# 2. GAME OBJECTS
# ---------------------------------------------------------------------------


class Dino:
    """
    The player character.
    State: RUNNING, JUMPING, or DUCKING.

    We draw the dino as simple coloured rectangles so no external art is
    needed.  A real game would swap sprite-sheets here instead of
    pygame.draw.rect.
    """

    WIDTH = 44
    HEIGHT = 48
    DUCK_HEIGHT = 28  # shorter hitbox when ducking
    X = 80  # fixed x-position

    def __init__(self) -> None:
        self.x: float = float(self.X)
        self.y: float = float(GROUND_Y - self.HEIGHT)
        self.vy: float = 0.0  # vertical velocity
        self.ducking: bool = False
        self.on_ground: bool = True

    # -- input abstraction (see core principle #3) ---------------------------

    def jump(self) -> None:
        if self.on_ground:
            self.vy = JUMP_VEL
            self.on_ground = False

    def duck(self, is_ducking: bool) -> None:
        self.ducking = is_ducking

    # -- physics update -------------------------------------------------------

    def update(self) -> None:
        # gravity
        if not self.on_ground:
            self.vy += GRAVITY
            self.y += self.vy
            # hit the floor?
            floor_y = GROUND_Y - (self.DUCK_HEIGHT if self.ducking else self.HEIGHT)
            if self.y >= floor_y:
                self.y = floor_y
                self.vy = 0
                self.on_ground = True

    # -- render ---------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        h = self.DUCK_HEIGHT if self.ducking else self.HEIGHT
        y = self.y

        body = pygame.Rect(self.x, y, self.WIDTH, h)
        pygame.draw.rect(screen, DARK, body)

        # eye
        eye_x = self.x + (30 if not self.ducking else 10)
        eye_y = self.y + 12
        pygame.draw.circle(screen, WHITE, (eye_x, eye_y), 4)

        # legs — little animated touch
        leg_offset = 3 if (pygame.time.get_ticks() // 150) % 2 == 0 else -3
        leg_y = self.y + h
        pygame.draw.rect(screen, DARK, (self.x + 8, leg_y, 6, 6 + leg_offset))
        pygame.draw.rect(screen, DARK, (self.x + 20, leg_y, 6, 6 - leg_offset))

    # -- hitbox for collisions -------------------------------------------------

    @property
    def rect(self) -> pygame.Rect:
        h = self.DUCK_HEIGHT if self.ducking else self.HEIGHT
        # pad the hitbox inward slightly to be forgiving
        return pygame.Rect(self.x + 4, self.y + 4, self.WIDTH - 8, h - 4)


class Obstacle:
    """
    Scrolling obstacle — cactus (tall / short) or pterodactyl (bird).

    Variants:
      0 = small cactus
      1 = tall cactus
      2 = bird (high)   — player must duck
      3 = bird (low)    — player must jump
    """

    # size presets for each variant
    SIZES = {
        0: (20, 40),  # small cactus
        1: (24, 54),  # tall cactus
        2: (42, 20),  # bird high  (flies above ground)
        3: (42, 20),  # bird low   (flies near ground)
    }
    BIRD_Y_OFFSETS = {2: 100, 3: 60}  # how high above ground the bird flies

    def __init__(self, variant: int) -> None:
        self.variant: int = variant
        w, h = self.SIZES[variant]
        self.width: int = w
        self.height: int = h

        self.x: float = float(SCREEN_W)
        if variant in (0, 1):  # cactus — sits on ground
            self.y = GROUND_Y - h
        else:  # bird — floats above ground
            self.y = GROUND_Y - h - self.BIRD_Y_OFFSETS[variant]

        self.speed = BASE_SPEED

    def update(self, speed: float) -> None:
        self.speed = speed
        self.x -= self.speed

    def is_off_screen(self) -> bool:
        return self.x + self.width < 0

    def draw(self, screen: pygame.Surface) -> None:
        rect = pygame.Rect(self.x, self.y, self.width, self.height)
        if self.variant in (0, 1):
            pygame.draw.rect(screen, GREY, rect)
        else:
            pygame.draw.rect(screen, (120, 120, 120), rect)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x + 2, self.y + 2, self.width - 4, self.height - 4)


class Ground:
    """
    Scrolling ground line with little dashes — gives the illusion of movement.
    """

    DASH_LENGTH = 12
    DASH_GAP = 6
    DASH_Y = GROUND_Y + 2

    def __init__(self) -> None:
        self.scroll: float = 0.0

    def update(self, speed: float) -> None:
        self.scroll = (self.scroll + speed) % (self.DASH_LENGTH + self.DASH_GAP)

    def draw(self, screen: pygame.Surface) -> None:
        # horizon line
        pygame.draw.line(screen, DARK, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 2)

        # scrolling dashes
        period = self.DASH_LENGTH + self.DASH_GAP
        x = -self.scroll
        while x < SCREEN_W:
            pygame.draw.line(
                screen,
                DARK,
                (x, self.DASH_Y),
                (x + self.DASH_LENGTH, self.DASH_Y),
                2,
            )
            x += period


# ---------------------------------------------------------------------------
# 3. GAME STATE MACHINE (core principle #1)
# ---------------------------------------------------------------------------
class Game:
    def __init__(self) -> None:
        self.state: str = "START"  # START | PLAYING | GAME_OVER
        self.dino: Dino = Dino()
        self.ground: Ground = Ground()
        self.obstacles: list[Obstacle] = []  # object-pool list (principle #2)
        self.score: int = 0
        self.high_score: int = 0
        self.speed: float = BASE_SPEED
        self.spawn_timer: int = 0
        self.next_spawn_in: int = random.randint(OBSTACLE_SPAWN_MIN, OBSTACLE_SPAWN_MAX)
        self.font: pygame.font.Font = pygame.font.Font(None, 24)
        self.big_font: pygame.font.Font = pygame.font.Font(None, 48)

    # -- helper ---------------------------------------------------------------

    def _reset(self) -> None:
        self.dino = Dino()
        self.obstacles.clear()
        self.score = 0
        self.speed = BASE_SPEED
        self.spawn_timer = 0
        self.next_spawn_in = random.randint(OBSTACLE_SPAWN_MIN, OBSTACLE_SPAWN_MAX)

    def _spawn_obstacle(self) -> None:
        # early game: mostly cacti.  later game: mix in birds.
        if self.score < 200:
            variant = random.randint(0, 1)  # cactus only
        elif self.score < 500:
            variant = random.choices([0, 1, 2], weights=[3, 3, 1])[0]
        else:
            variant = random.choices([0, 1, 2, 3], weights=[2, 2, 2, 1])[0]
        self.obstacles.append(Obstacle(variant))

    # -- update per frame -----------------------------------------------------

    def update(self) -> None:
        if self.state != "PLAYING":
            return

        # --- speed ramps up with score (principle #4: progressive difficulty)
        self.speed = min(MAX_SPEED, BASE_SPEED + self.score * SPEED_UP_PER_POINT)

        # --- dino
        self.dino.update()

        # --- ground
        self.ground.update(self.speed)

        # --- obstacles: move, cull off-screen, spawn new
        for obs in self.obstacles:
            obs.update(self.speed)

        # cull
        self.obstacles = [o for o in self.obstacles if not o.is_off_screen()]

        # spawn
        self.spawn_timer += 1
        if self.spawn_timer >= self.next_spawn_in:
            self._spawn_obstacle()
            self.spawn_timer = 0
            # spawn windows get tighter as speed increases
            spawn_min = max(25, OBSTACLE_SPAWN_MIN - int(self.speed - BASE_SPEED) * 3)
            spawn_max = max(50, OBSTACLE_SPAWN_MAX - int(self.speed - BASE_SPEED) * 6)
            self.next_spawn_in = random.randint(spawn_min, spawn_max)

        # --- score (1 point per 6 frames at base speed)
        self.score += 1

        # --- collision check (AABB — core principle #6)
        dino_rect = self.dino.rect
        for obs in self.obstacles:
            if dino_rect.colliderect(obs.rect):
                self.state = "GAME_OVER"
                if self.score > self.high_score:
                    self.high_score = self.score
                return

    # -- render ---------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(WHITE)

        self.ground.draw(screen)
        self.dino.draw(screen)
        for obs in self.obstacles:
            obs.draw(screen)

        # --- HUD ---
        score_surf = self.font.render(f"Score: {self.score:05d}", True, GREY)
        screen.blit(score_surf, (SCREEN_W - 150, 20))

        hi_surf = self.font.render(f"HI: {self.high_score:05d}", True, GREY)
        screen.blit(hi_surf, (SCREEN_W - 300, 20))

        # --- state overlays ---
        if self.state == "START":
            self._draw_overlay(screen, "DINO SHRED", "Press SPACE  or  ↑  to start")
        elif self.state == "GAME_OVER":
            self._draw_overlay(screen, "GAME OVER", "Press SPACE  or  ↑  to retry")

    def _draw_overlay(self, screen: pygame.Surface, title: str, subtitle: str) -> None:
        # semi-transparent backdrop
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((255, 255, 255, 120))
        screen.blit(s, (0, 0))

        t = self.big_font.render(title, True, DARK)
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2 - 80))

        st = self.font.render(subtitle, True, GREY)
        screen.blit(st, (SCREEN_W // 2 - st.get_width() // 2, SCREEN_H // 2 - 30))

    # -- input abstraction (core principle #3) ---------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_UP):
                if self.state == "START":
                    self.state = "PLAYING"
                elif self.state == "GAME_OVER":
                    self._reset()
                    self.state = "PLAYING"
                elif self.state == "PLAYING":
                    self.dino.jump()

            if event.key == pygame.K_DOWN and self.state == "PLAYING":
                self.dino.duck(True)

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_DOWN and self.state == "PLAYING":
                self.dino.duck(False)


# ---------------------------------------------------------------------------
# 4. GAME LOOP — the heart of every game (core principle #1)
# ---------------------------------------------------------------------------


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Dino Shred")
    clock = pygame.time.Clock()

    game = Game()

    while True:
        # ---- INPUT ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        # ---- UPDATE ----
        game.update()

        # ---- RENDER ----
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
