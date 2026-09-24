"""The conductor: the beat grid as pure functions of the stream clock (ADR 0004).

Nothing here is ever advanced or accumulated — every quantity is derived fresh
from a timestamp, so there is no error to accumulate and nothing to drift.
"""

import math


class Conductor:
    def __init__(self, t0: float, bpm: float) -> None:
        self.t0 = t0
        self.bpm = bpm

    @property
    def period(self) -> float:
        return 60.0 / self.bpm

    def beat_time(self, n: int) -> float:
        return self.t0 + n * self.period

    def nearest_beat(self, t: float) -> int:
        return round((t - self.t0) / self.period)

    def beats_in(self, t_start: float, t_end: float) -> range:
        """All beat indices n with t_start <= beat_time(n) < t_end."""
        first = math.ceil((t_start - self.t0) / self.period)
        stop = math.ceil((t_end - self.t0) / self.period)
        return range(first, stop)


__all__ = ["Conductor"]
