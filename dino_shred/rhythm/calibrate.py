"""Latency calibration (spec 3.6): chug along with the click; the median error
is the constant part of detector delay + player bias. MAD rejection discards
wild outliers (missed/extra hits) before taking the median.
"""

import statistics

from dino_shred.rhythm.conductor import Conductor


def compute_offset(errors: list[float]) -> tuple[float, float]:
    med = statistics.median(errors)
    mad = statistics.median(abs(e - med) for e in errors)
    kept = [e for e in errors if abs(e - med) <= 3.0 * mad] if mad > 0.0 else list(errors)
    return statistics.median(kept), mad


class CalibrationSession:
    def __init__(self, conductor: Conductor, min_hits: int = 20, discard: int = 4) -> None:
        self.conductor = conductor
        self.min_hits = min_hits
        self.discard = discard
        self._errors: list[float] = []

    def add_onset(self, onset_t: float) -> None:
        n = self.conductor.nearest_beat(onset_t)
        self._errors.append(onset_t - self.conductor.beat_time(n))

    @property
    def hits(self) -> int:
        return max(0, len(self._errors) - self.discard)

    @property
    def is_complete(self) -> bool:
        return self.hits >= self.min_hits

    def result(self) -> tuple[float, float]:
        return compute_offset(self._errors[self.discard :])


__all__ = ["CalibrationSession", "compute_offset"]
