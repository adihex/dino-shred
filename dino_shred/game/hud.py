"""HUD: per-hit judgment popups, streak, live error bar, session histogram.

Pure helpers (formatting, bar mapping, binning) are unit-tested; the draw
methods are thin pygame rendering over them. Sign convention: negative = early.
"""

import pygame

from dino_shred import config
from dino_shred.rhythm.judge import Grade, Judgment

GRADE_COLORS: dict[Grade, tuple[int, int, int]] = {
    Grade.PERFECT: (46, 160, 67),
    Grade.GOOD: (9, 105, 218),
    Grade.OK: (154, 103, 0),
    Grade.MISS: (207, 34, 46),
    Grade.OFF_GRID: (110, 119, 129),
}

POPUP_LIFETIME_S = 0.8


def format_error(error_s: float | None) -> str:
    if error_s is None:
        return "MISS"
    ms = round(error_s * 1000)
    return f"{ms:+d} ms {'early' if ms < 0 else 'late'}"


def error_bar_x(error_s: float, width: int, max_s: float = 0.1) -> int:
    clamped = max(-max_s, min(max_s, error_s))
    return round((clamped + max_s) / (2 * max_s) * width)


def histogram_bins(errors: list[float], n_bins: int = 20, range_s: float = 0.1) -> list[int]:
    bins = [0] * n_bins
    for e in errors:
        frac = (max(-range_s, min(range_s, e)) + range_s) / (2 * range_s)
        bins[min(n_bins - 1, int(frac * n_bins))] += 1
    return bins


class Hud:
    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 40)
        self._popup: tuple[Judgment, float] | None = None  # (judgment, born_t)

    def add(self, judgment: Judgment, t: float) -> None:
        self._popup = (judgment, t)

    def draw(self, screen: pygame.Surface, t: float, streak: int, bpm: float) -> None:
        info = self.font.render(f"streak {streak}   {bpm:g} BPM", True, config.GREY)
        screen.blit(info, (config.SCREEN_W - info.get_width() - 20, 20))

        if self._popup is not None:
            judgment, born = self._popup
            if t - born > POPUP_LIFETIME_S:
                self._popup = None
            else:
                color = GRADE_COLORS[judgment.grade]
                name = self.big_font.render(judgment.grade.name, True, color)
                screen.blit(name, (config.SCREEN_W // 2 - name.get_width() // 2, 60))
                if judgment.error_s is not None:
                    detail = self.font.render(format_error(judgment.error_s), True, color)
                    screen.blit(detail, (config.SCREEN_W // 2 - detail.get_width() // 2, 96))
                    # live error bar: | early ... 0 ... late |
                    bar = pygame.Rect(config.SCREEN_W // 2 - 100, 124, 200, 6)
                    pygame.draw.rect(screen, config.GREY, bar, 1)
                    pygame.draw.line(screen, config.GREY, (bar.centerx, 120), (bar.centerx, 134))
                    x = bar.x + error_bar_x(judgment.error_s, bar.width)
                    pygame.draw.circle(screen, color, (x, bar.centery), 5)

    def draw_summary(
        self,
        screen: pygame.Surface,
        errors: list[float],
        counts: dict[Grade, int],
        best_streak: int,
    ) -> None:
        lines = [f"best streak {best_streak}"] + [
            f"{g.name.lower()} {counts[g]}"
            for g in (Grade.PERFECT, Grade.GOOD, Grade.OK, Grade.MISS)
        ]
        for i, text in enumerate(lines):
            surf = self.font.render(text, True, config.DARK)
            screen.blit(surf, (60, 150 + i * 26))

        bins = histogram_bins(errors)
        if errors:
            top = max(bins)
            base_y, h_max, w = 300, 80, 10
            for i, count in enumerate(bins):
                h = 0 if top == 0 else round(count / top * h_max)
                pygame.draw.rect(
                    screen, config.DARK, pygame.Rect(300 + i * (w + 2), base_y - h, w, h)
                )
            label = self.font.render("early   <- timing ->   late", True, config.GREY)
            screen.blit(label, (300, base_y + 8))


__all__ = ["GRADE_COLORS", "Hud", "error_bar_x", "format_error", "histogram_bins"]
