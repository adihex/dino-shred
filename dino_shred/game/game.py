"""The rhythm game state machine (spec 3.7).

States: MENU -> CALIBRATE -> MENU -> PLAYING -> GAME_OVER -> (retry) PLAYING.
The game never reads the audio clock itself — the app passes stream time `t`
into update()/draw(), and onsets arrive pre-timestamped. That keeps this whole
module headless-testable with a fake clock.
"""

from collections.abc import Callable
from enum import Enum

import pygame

from dino_shred import config
from dino_shred.audio.detect import OnsetEvent
from dino_shred.game.hud import Hud
from dino_shred.game.objects import Dino, Ground, Obstacle
from dino_shred.game.spawner import Spawner
from dino_shred.rhythm.calibrate import CalibrationSession
from dino_shred.rhythm.conductor import Conductor
from dino_shred.rhythm.judge import Judge, Judgment


class State(Enum):
    MENU = "menu"
    CALIBRATE = "calibrate"
    PLAYING = "playing"
    GAME_OVER = "game_over"


LEAD_IN_S = 1.0


class RhythmGame:
    def __init__(self, bpm: float = 80.0, offset_s: float = 0.0, count_in_beats: int = 4) -> None:
        self.bpm = bpm
        self.offset_s = offset_s
        self.count_in_beats = count_in_beats
        self.state = State.MENU
        self.dino = Dino()
        self.ground = Ground()
        self.hud = Hud()
        self.banner = ""  # watchdog messages, set by the app
        self.conductor: Conductor | None = None
        self.judge: Judge | None = None
        self.spawner: Spawner | None = None
        self.calibration: CalibrationSession | None = None
        self.calibration_result: tuple[float, float] | None = None
        self.obstacles: list[Obstacle] = []
        self.on_conductor_change: Callable[[Conductor], None] | None = None
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 48)

    # -- state transitions -------------------------------------------------------

    def _new_grid(self, t_now: float) -> Conductor:
        self.conductor = Conductor(t0=t_now + LEAD_IN_S, bpm=self.bpm)
        if self.on_conductor_change is not None:
            self.on_conductor_change(self.conductor)
        return self.conductor

    def start_playing(self, t_now: float) -> None:
        conductor = self._new_grid(t_now)
        self.dino = Dino()
        self.obstacles = []
        self.judge = Judge(conductor, offset_s=self.offset_s, first_beat=self.count_in_beats)
        self.spawner = Spawner(conductor, first_beat=self.count_in_beats)
        self.state = State.PLAYING

    def start_calibration(self, t_now: float) -> None:
        conductor = self._new_grid(t_now)
        self.calibration = CalibrationSession(conductor)
        self.calibration_result = None
        self.state = State.CALIBRATE

    # -- inputs --------------------------------------------------------------------

    def handle_onset(self, ev: OnsetEvent) -> None:
        if self.state is State.PLAYING and self.judge is not None:
            self.dino.jump()
            judgment: Judgment = self.judge.judge_onset(ev.t)
            self.hud.add(judgment, ev.t)
        elif self.state is State.CALIBRATE and self.calibration is not None:
            self.calibration.add_onset(ev.t)

    def handle_key(self, key: int, down: bool, t_now: float) -> None:
        if key == pygame.K_SPACE and down:
            if self.state in (State.MENU, State.GAME_OVER):
                self.start_playing(t_now)
            elif self.state in (State.PLAYING, State.CALIBRATE):
                # keyboard fallback: a synthetic onset at "now"
                self.handle_onset(OnsetEvent(t=t_now, strength=1.0, detector="keyboard"))
        elif key == pygame.K_c and down and self.state is State.MENU:
            self.start_calibration(t_now)
        elif key == pygame.K_DOWN and self.state is State.PLAYING:
            self.dino.duck(down)

    # -- per-frame update ------------------------------------------------------------

    def update(self, t: float) -> None:
        if self.state is State.PLAYING:
            assert self.judge is not None and self.spawner is not None
            self.dino.update()
            self.ground.update(config.PX_PER_SEC / config.FPS)
            self.obstacles.extend(self.spawner.update(t))
            self.obstacles = [o for o in self.obstacles if not o.is_gone(t)]
            for miss in self.judge.sweep_misses(t):
                self.hud.add(miss, t)
            dino_rect = self.dino.rect
            for obs in self.obstacles:
                if dino_rect.colliderect(obs.rect(t)):
                    self.state = State.GAME_OVER
                    return
        elif self.state is State.CALIBRATE:
            assert self.calibration is not None
            if self.calibration.is_complete:
                self.calibration_result = self.calibration.result()
                self.offset_s = self.calibration_result[0]
                self.state = State.MENU

    # -- render ----------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, t: float) -> None:
        screen.fill(config.WHITE)
        self.ground.draw(screen)
        self.dino.draw(screen)
        for obs in self.obstacles:
            obs.draw(screen, t)

        if self.state is State.PLAYING:
            assert self.judge is not None and self.conductor is not None
            self.hud.draw(screen, t, self.judge.streak, self.bpm)
            # beat pulse: flash a dot for 100 ms after each beat
            phase = (t - self.conductor.t0) % self.conductor.period
            if 0 <= phase < 0.1:
                pygame.draw.circle(screen, config.DARK, (40, 40), 10)
        elif self.state is State.MENU:
            self._overlay(screen, "DINO SHRED", "SPACE/chug to play - C to calibrate")
        elif self.state is State.CALIBRATE:
            assert self.calibration is not None
            self._overlay(
                screen, "CALIBRATE",
                f"chug with the click - {self.calibration.hits}/{self.calibration.min_hits}",
            )
        elif self.state is State.GAME_OVER:
            assert self.judge is not None
            self._overlay(screen, "GAME OVER", "SPACE/chug to retry")
            self.hud.draw_summary(
                screen, self.judge.errors, self.judge.counts, self.judge.best_streak
            )

        if self.banner:
            warn = self.font.render(self.banner, True, (207, 34, 46))
            screen.blit(warn, (20, config.SCREEN_H - 30))

    def _overlay(self, screen: pygame.Surface, title: str, subtitle: str) -> None:
        s = pygame.Surface((config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA)
        s.fill((255, 255, 255, 120))
        screen.blit(s, (0, 0))
        t_surf = self.big_font.render(title, True, config.DARK)
        screen.blit(t_surf, (config.SCREEN_W // 2 - t_surf.get_width() // 2, 100))
        st = self.font.render(subtitle, True, config.GREY)
        screen.blit(st, (config.SCREEN_W // 2 - st.get_width() // 2, 150))


__all__ = ["LEAD_IN_S", "RhythmGame", "State"]
