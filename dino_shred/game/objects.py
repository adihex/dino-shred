"""Game objects. Ported from main.py; physics constants now derived in config."""

import pygame

from dino_shred import config
from dino_shred.rhythm.conductor import Conductor


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

    def __init__(self) -> None:
        self.x: float = float(config.DINO_X)
        self.y: float = float(config.GROUND_Y - self.HEIGHT)
        self.vy: float = 0.0  # vertical velocity
        self.ducking: bool = False
        self.on_ground: bool = True

    # -- input abstraction (see core principle #3) ---------------------------

    def jump(self) -> None:
        if self.on_ground:
            self.vy = config.JUMP_VEL
            self.on_ground = False

    def duck(self, is_ducking: bool) -> None:
        self.ducking = is_ducking

    # -- physics update -------------------------------------------------------

    def update(self) -> None:
        # gravity
        if not self.on_ground:
            self.vy += config.GRAVITY
            self.y += self.vy
            # hit the floor?
            floor_y = config.GROUND_Y - (self.DUCK_HEIGHT if self.ducking else self.HEIGHT)
            if self.y >= floor_y:
                self.y = floor_y
                self.vy = 0
                self.on_ground = True

    # -- render ---------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        h = self.DUCK_HEIGHT if self.ducking else self.HEIGHT
        y = self.y

        body = pygame.Rect(self.x, y, self.WIDTH, h)
        pygame.draw.rect(screen, config.DARK, body)

        # eye
        eye_x = self.x + (30 if not self.ducking else 10)
        eye_y = self.y + 12
        pygame.draw.circle(screen, config.WHITE, (eye_x, eye_y), 4)

        # legs — little animated touch
        leg_offset = 3 if (pygame.time.get_ticks() // 150) % 2 == 0 else -3
        leg_y = self.y + h
        pygame.draw.rect(screen, config.DARK, (self.x + 8, leg_y, 6, 6 + leg_offset))
        pygame.draw.rect(screen, config.DARK, (self.x + 20, leg_y, 6, 6 - leg_offset))

    # -- hitbox for collisions -------------------------------------------------

    @property
    def rect(self) -> pygame.Rect:
        h = self.DUCK_HEIGHT if self.ducking else self.HEIGHT
        # pad the hitbox inward slightly to be forgiving
        return pygame.Rect(self.x + 4, self.y + 4, self.WIDTH - 8, h - 4)


class Ground:
    """
    Scrolling ground line with little dashes — gives the illusion of movement.
    """

    DASH_LENGTH = 12
    DASH_GAP = 6
    DASH_Y = config.GROUND_Y + 2

    def __init__(self) -> None:
        self.scroll: float = 0.0

    def update(self, speed: float) -> None:
        self.scroll = (self.scroll + speed) % (self.DASH_LENGTH + self.DASH_GAP)

    def draw(self, screen: pygame.Surface) -> None:
        # horizon line
        pygame.draw.line(
            screen,
            config.DARK,
            (0, config.GROUND_Y),
            (config.SCREEN_W, config.GROUND_Y),
            2,
        )

        # scrolling dashes
        period = self.DASH_LENGTH + self.DASH_GAP
        x = -self.scroll
        while x < config.SCREEN_W:
            pygame.draw.line(
                screen,
                config.DARK,
                (x, self.DASH_Y),
                (x + self.DASH_LENGTH, self.DASH_Y),
                2,
            )
            x += period


class Obstacle:
    """A cactus bound to a beat: its position is DERIVED from time (ADR 0004).

    x(t) is computed fresh every frame from the conductor — never integrated —
    so the obstacle's center crosses the dino's center exactly at beat_time(n).
    Variants: 0 = small cactus, 1 = tall cactus. (Birds return with the chug
    classifier in M5 — a guitar can't duck yet.)
    """

    SIZES = {0: (20, 40), 1: (24, 54)}

    def __init__(self, beat_n: int, conductor: Conductor, variant: int) -> None:
        self.beat_n = beat_n
        self.conductor = conductor
        self.variant = variant
        self.width, self.height = self.SIZES[variant]
        self.y = config.GROUND_Y - self.height
        # align obstacle center with dino center at the beat
        dino_center = config.DINO_X + Dino.WIDTH / 2
        self._x_at_beat = dino_center - self.width / 2

    def x(self, t: float) -> float:
        dt = self.conductor.beat_time(self.beat_n) - t
        return self._x_at_beat + dt * config.PX_PER_SEC

    def rect(self, t: float) -> pygame.Rect:
        x = self.x(t)
        return pygame.Rect(int(x) + 2, self.y + 2, self.width - 4, self.height - 4)

    def is_gone(self, t: float) -> bool:
        return self.x(t) + self.width < -50

    def draw(self, screen: pygame.Surface, t: float) -> None:
        pygame.draw.rect(
            screen, config.GREY, pygame.Rect(int(self.x(t)), self.y, self.width, self.height)
        )
