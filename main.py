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
SKY_BLUE = (135, 206, 235)
STITCH_BLUE = (0, 112, 204)
STITCH_LIGHT_BLUE = (102, 178, 255)
STITCH_EAR_PINK = (255, 153, 204)
GRASS_GREEN = (34, 139, 34)
DIRT_BROWN = (139, 69, 19)
WOOD_BROWN = (160, 82, 45)
LEAF_GREEN = (50, 205, 50)

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

        # Stitch body
        body = pygame.Rect(self.x + 4, y + 10, self.WIDTH - 8, h - 10)
        pygame.draw.rect(screen, STITCH_BLUE, body, border_radius=8)

        # Stitch belly/chest (lighter blue)
        belly = pygame.Rect(self.x + 8, y + 20, self.WIDTH - 16, h - 20)
        pygame.draw.rect(screen, STITCH_LIGHT_BLUE, belly, border_radius=6)

        # Stitch head
        head_y = y if not self.ducking else y + 10
        head_w = self.WIDTH
        head_h = 24
        pygame.draw.ellipse(screen, STITCH_BLUE, (self.x, head_y, head_w, head_h))

        # Big ears
        ear_width = 16
        ear_height = 8
        if not self.ducking:
            # Left ear
            pygame.draw.ellipse(
                screen, STITCH_BLUE, (self.x - 10, head_y + 4, ear_width, ear_height)
            )
            pygame.draw.ellipse(
                screen, STITCH_EAR_PINK, (self.x - 8, head_y + 5, ear_width - 4, ear_height - 2)
            )
            # Right ear
            pygame.draw.ellipse(
                screen, STITCH_BLUE, (self.x + head_w - 6, head_y + 4, ear_width, ear_height)
            )
            pygame.draw.ellipse(
                screen,
                STITCH_EAR_PINK,
                (self.x + head_w - 4, head_y + 5, ear_width - 4, ear_height - 2),
            )
        else:
            # Pinned back ears when ducking
            pygame.draw.ellipse(
                screen, STITCH_BLUE, (self.x - 14, head_y + 8, ear_width, ear_height)
            )
            pygame.draw.ellipse(
                screen, STITCH_EAR_PINK, (self.x - 12, head_y + 9, ear_width - 4, ear_height - 2)
            )
            pygame.draw.ellipse(
                screen, STITCH_BLUE, (self.x + head_w - 2, head_y + 8, ear_width, ear_height)
            )
            pygame.draw.ellipse(
                screen,
                STITCH_EAR_PINK,
                (self.x + head_w, head_y + 9, ear_width - 4, ear_height - 2),
            )

        # Big eyes
        eye_spacing = 14
        eye_y = head_y + 6
        eye_x_left = self.x + 12
        eye_x_right = eye_x_left + eye_spacing

        # Outer eye (dark/black part)
        pygame.draw.ellipse(screen, BLACK, (eye_x_left, eye_y, 8, 10))
        pygame.draw.ellipse(screen, BLACK, (eye_x_right, eye_y, 8, 10))
        # Inner eye (pupil shine)
        pygame.draw.circle(screen, WHITE, (eye_x_left + 4, eye_y + 3), 2)
        pygame.draw.circle(screen, WHITE, (eye_x_right + 4, eye_y + 3), 2)

        # Little nose
        pygame.draw.ellipse(screen, DARK, (self.x + 18, head_y + 14, 6, 4))

        # legs — little animated touch
        leg_offset = 3 if (pygame.time.get_ticks() // 150) % 2 == 0 else -3
        leg_y = self.y + h - 2
        pygame.draw.rect(
            screen, STITCH_BLUE, (self.x + 12, leg_y, 6, 6 + leg_offset), border_radius=2
        )
        pygame.draw.rect(
            screen, STITCH_BLUE, (self.x + 24, leg_y, 6, 6 - leg_offset), border_radius=2
        )

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
        if self.variant in (0, 1):
            # Alien plant / Palm tree trunk
            trunk_w = 8
            trunk_x = self.x + (self.width - trunk_w) // 2
            pygame.draw.rect(screen, WOOD_BROWN, (trunk_x, self.y + 10, trunk_w, self.height - 10))

            # Alien plant leaves
            leaf_color = LEAF_GREEN
            if self.variant == 0:
                # Small plant
                pygame.draw.ellipse(screen, leaf_color, (self.x, self.y, self.width, 20))
            else:
                # Tall plant (multiple layers)
                pygame.draw.ellipse(screen, leaf_color, (self.x, self.y, self.width, 20))
                pygame.draw.ellipse(
                    screen, leaf_color, (self.x - 4, self.y + 10, self.width + 8, 20)
                )
        else:
            # Alien bird/creature
            wing_offset = 6 if (pygame.time.get_ticks() // 150) % 2 == 0 else -6
            body_color = (200, 50, 50)  # Red alien bird

            # body
            pygame.draw.ellipse(screen, body_color, (self.x + 8, self.y + 8, self.width - 16, 12))

            # wings
            pygame.draw.polygon(
                screen,
                body_color,
                [
                    (self.x + self.width // 2, self.y + 10),
                    (self.x + self.width // 2 - 10, self.y + 10 + wing_offset),
                    (self.x + self.width // 2 + 10, self.y + 10 + wing_offset),
                ],
            )

            # head
            pygame.draw.circle(screen, body_color, (int(self.x + 12), int(self.y + 10)), 6)
            # eye
            pygame.draw.circle(screen, WHITE, (int(self.x + 10), int(self.y + 8)), 2)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x + 2, self.y + 2, self.width - 4, self.height - 4)


class Cloud:
    """
    Scrolling cloud in the background.
    """

    def __init__(self) -> None:
        self.x: float = random.randint(SCREEN_W, SCREEN_W + 400)
        self.y: float = random.randint(20, 150)
        self.speed: float = BASE_SPEED * 0.2 + random.random() * 1.5
        self.scale: float = random.uniform(0.6, 1.2)

    def update(self, speed: float) -> None:
        self.x -= self.speed * (speed / BASE_SPEED)
        if self.x < -100:
            self.x = random.randint(SCREEN_W, SCREEN_W + 100)
            self.y = random.randint(20, 150)

    def draw(self, screen: pygame.Surface) -> None:
        # draw a simple cloud shape using circles
        r = int(20 * self.scale)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), r)
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.x + 20 * self.scale), int(self.y + 10 * self.scale)),
            int(15 * self.scale),
        )
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.x - 20 * self.scale), int(self.y + 10 * self.scale)),
            int(15 * self.scale),
        )
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.x + 35 * self.scale), int(self.y + 20 * self.scale)),
            int(12 * self.scale),
        )
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.x - 35 * self.scale), int(self.y + 20 * self.scale)),
            int(12 * self.scale),
        )
        # base rect
        pygame.draw.rect(
            screen,
            WHITE,
            (
                int(self.x - 35 * self.scale),
                int(self.y + 10 * self.scale),
                int(70 * self.scale),
                int(22 * self.scale),
            ),
        )


class Ground:
    """
    Scrolling ground line with little dashes — gives the illusion of movement.
    """

    DASH_LENGTH = 12
    DASH_GAP = 6
    DASH_Y = GROUND_Y + 10

    def __init__(self) -> None:
        self.scroll: float = 0.0

    def update(self, speed: float) -> None:
        self.scroll = (self.scroll + speed) % (self.DASH_LENGTH + self.DASH_GAP)

    def draw(self, screen: pygame.Surface) -> None:
        # grass
        pygame.draw.rect(screen, GRASS_GREEN, (0, GROUND_Y, SCREEN_W, SCREEN_H - GROUND_Y))
        # dirt below grass
        pygame.draw.rect(screen, DIRT_BROWN, (0, GROUND_Y + 20, SCREEN_W, SCREEN_H - GROUND_Y - 20))
        # horizon line
        pygame.draw.line(screen, DARK, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 2)

        # scrolling dashes for dirt texture
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
            pygame.draw.line(
                screen,
                DARK,
                (x + period // 2, self.DASH_Y + 15),
                (x + period // 2 + self.DASH_LENGTH, self.DASH_Y + 15),
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
        self.clouds: list[Cloud] = [Cloud() for _ in range(3)]
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

        # --- background
        for cloud in self.clouds:
            cloud.update(self.speed)

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
        screen.fill(SKY_BLUE)

        for cloud in self.clouds:
            cloud.draw(screen)

        self.ground.draw(screen)
        self.dino.draw(screen)
        for obs in self.obstacles:
            obs.draw(screen)

        # --- HUD ---
        # Draw shadow
        score_shadow = self.font.render(f"Score: {self.score:05d}", True, BLACK)
        screen.blit(score_shadow, (SCREEN_W - 149, 21))
        score_surf = self.font.render(f"Score: {self.score:05d}", True, WHITE)
        screen.blit(score_surf, (SCREEN_W - 150, 20))

        hi_shadow = self.font.render(f"HI: {self.high_score:05d}", True, BLACK)
        screen.blit(hi_shadow, (SCREEN_W - 299, 21))
        hi_surf = self.font.render(f"HI: {self.high_score:05d}", True, WHITE)
        screen.blit(hi_surf, (SCREEN_W - 300, 20))

        # --- state overlays ---
        if self.state == "START":
            self._draw_overlay(screen, "STITCH RUNNER", "Press SPACE  or  ↑  to start")
        elif self.state == "GAME_OVER":
            self._draw_overlay(screen, "GAME OVER", "Press SPACE  or  ↑  to retry")

    def _draw_overlay(self, screen: pygame.Surface, title: str, subtitle: str) -> None:
        # semi-transparent backdrop with a bit of a blue tint
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((0, 50, 150, 100))
        screen.blit(s, (0, 0))

        # title with shadow
        ts = self.big_font.render(title, True, BLACK)
        screen.blit(ts, (SCREEN_W // 2 - ts.get_width() // 2 + 2, SCREEN_H // 2 - 78))
        t = self.big_font.render(title, True, WHITE)
        screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 2 - 80))

        # subtitle with shadow
        sts = self.font.render(subtitle, True, BLACK)
        screen.blit(sts, (SCREEN_W // 2 - sts.get_width() // 2 + 1, SCREEN_H // 2 - 29))
        st = self.font.render(subtitle, True, (200, 230, 255))
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
