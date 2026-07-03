"""Onset detectors, built from scratch (ADR 0003).

Stage 1 — EnergyGate: per-hop RMS in dB with a rising-edge threshold,
hysteresis re-arming, and a refractory period. Runs inside the audio
callback: no allocation, O(hop) work, all state is a few floats.

The protocol every detector implements:
    process(frame: np.float32[hop], t_frame: float) -> OnsetEvent | None
`t_frame` is the stream-clock time of frame[0] (inputBufferAdcTime + offset).
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OnsetEvent:
    t: float  # stream-clock seconds of the hit
    strength: float  # dB above threshold
    detector: str


class EnergyGate:
    def __init__(
        self,
        sample_rate: int = 48000,
        hop: int = 256,
        threshold_db: float = -30.0,
        hysteresis_db: float = 6.0,
        refractory_s: float = 0.08,
    ) -> None:
        self.sample_rate = sample_rate
        self.hop = hop
        self.threshold_db = threshold_db
        self.hysteresis_db = hysteresis_db
        self.refractory_s = refractory_s
        self._armed = True
        self._last_onset_t = -1e9

    def process(self, frame: np.ndarray, t_frame: float) -> OnsetEvent | None:
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
        rms_db = 20.0 * float(np.log10(rms + 1e-10))

        if self._armed and rms_db >= self.threshold_db:
            self._armed = False
            if t_frame - self._last_onset_t >= self.refractory_s:
                self._last_onset_t = t_frame
                return OnsetEvent(
                    t=t_frame, strength=rms_db - self.threshold_db, detector="energy"
                )
        elif not self._armed and rms_db < self.threshold_db - self.hysteresis_db:
            self._armed = True  # signal decayed: re-arm for the next attack
        return None


__all__ = ["EnergyGate", "OnsetEvent"]
