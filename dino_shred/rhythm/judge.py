"""Judgment: error = onset_t - offset - beat_time(nearest)  (ADR 0004).

Windows are half-widths; negative error = early. Game rule (spec 3.5): the
player chugs every beat; a missed beat resets the streak; off-grid extras
never affect score. sweep_misses() trails `now` by a safety margin so an
onset still sitting in the event queue can claim its beat.
"""

from dataclasses import dataclass
from enum import Enum

from dino_shred.rhythm.conductor import Conductor


class Grade(Enum):
    PERFECT = "perfect"
    GOOD = "good"
    OK = "ok"
    MISS = "miss"
    OFF_GRID = "off_grid"


WINDOWS: dict[Grade, float] = {
    Grade.PERFECT: 0.030,
    Grade.GOOD: 0.060,
    Grade.OK: 0.100,
}
_EPS = 1e-12


@dataclass(frozen=True)
class Judgment:
    grade: Grade
    beat_n: int
    error_s: float | None  # None for MISS


class Judge:
    def __init__(
        self,
        conductor: Conductor,
        offset_s: float = 0.0,
        first_beat: int = 0,
        max_window_s: float = 0.100,
        sweep_margin_s: float = 0.05,
    ) -> None:
        self.conductor = conductor
        self.offset_s = offset_s
        self.first_beat = first_beat
        self.max_window_s = max_window_s
        self.sweep_margin_s = sweep_margin_s
        self.streak = 0
        self.best_streak = 0
        self.counts: dict[Grade, int] = dict.fromkeys(Grade, 0)
        self.errors: list[float] = []
        self._consumed: set[int] = set()
        self._next_sweep = first_beat

    def judge_onset(self, onset_t: float) -> Judgment:
        t = onset_t - self.offset_s
        n = self.conductor.nearest_beat(t)
        error = t - self.conductor.beat_time(n)
        claimable = (
            n >= self.first_beat
            and n >= self._next_sweep
            and n not in self._consumed
            and abs(error) <= self.max_window_s + _EPS
        )
        if not claimable:
            self.counts[Grade.OFF_GRID] += 1
            return Judgment(Grade.OFF_GRID, n, error)

        self._consumed.add(n)
        grade = self._grade_for_error(error)
        self.counts[grade] += 1
        self.errors.append(error)
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        return Judgment(grade, n, error)

    def sweep_misses(self, now: float) -> list[Judgment]:
        """Mark beats whose claim window has fully passed and that got no onset."""
        t = now - self.offset_s - self.sweep_margin_s
        misses: list[Judgment] = []
        while self.conductor.beat_time(self._next_sweep) + self.max_window_s < t:
            n = self._next_sweep
            self._next_sweep += 1
            if n in self._consumed:
                self._consumed.discard(n)
            else:
                self.counts[Grade.MISS] += 1
                self.streak = 0
                misses.append(Judgment(Grade.MISS, n, None))
        return misses

    def _grade_for_error(self, error: float) -> Grade:
        abs_error = abs(error)
        if abs_error <= WINDOWS[Grade.PERFECT] + _EPS:
            return Grade.PERFECT
        if abs_error <= WINDOWS[Grade.GOOD] + _EPS:
            return Grade.GOOD
        return Grade.OK


__all__ = ["WINDOWS", "Grade", "Judge", "Judgment"]
