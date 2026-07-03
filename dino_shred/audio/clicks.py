"""Metronome click synthesis + sample-accurate scheduling into DAC buffers (ADR 0002).

render() is called from the real-time audio callback: it must not allocate.
All waveforms are preallocated in __init__; scheduling is stateless — a click
whose beat fell before this buffer but whose tail reaches into it is recomputed
from the beat time, so block boundaries are invisible.
"""

import numpy as np

from dino_shred.rhythm.conductor import Conductor


def make_click(
    sr: int = 48000, freq: float = 1000.0, dur_ms: float = 5.0, amp: float = 0.5
) -> np.ndarray:
    n = int(sr * dur_ms / 1000.0)
    t = (np.arange(n, dtype=np.float32) + 0.5) / sr
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-t / (dur_ms / 5000.0))
    return (amp * wave / np.abs(wave).max()).astype(np.float32)


class ClickScheduler:
    def __init__(self, conductor: Conductor, sr: int = 48000, beats_per_bar: int = 4) -> None:
        self.conductor = conductor
        self.sr = sr
        self.beats_per_bar = beats_per_bar
        self.click = make_click(sr)
        self.accent = make_click(sr, freq=1500.0, amp=0.8)

    def render(self, dac_time: float, out: np.ndarray) -> None:
        """Add clicks into `out`, which covers [dac_time, dac_time + len(out)/sr)."""
        frames = len(out)
        window_end = dac_time + frames / self.sr
        lookback = dac_time - len(self.accent) / self.sr  # catch tails from earlier beats
        for n in self.conductor.beats_in(lookback, window_end):
            if n < 0:
                continue
            wave = self.accent if n % self.beats_per_bar == 0 else self.click
            offset = round((self.conductor.beat_time(n) - dac_time) * self.sr)
            src_lo = max(0, -offset)
            dst_lo = max(0, offset)
            length = min(len(wave) - src_lo, frames - dst_lo)
            if length > 0:
                out[dst_lo : dst_lo + length] += wave[src_lo : src_lo + length]


__all__ = ["ClickScheduler", "make_click"]
