import numpy as np

from dino_shred.audio.clicks import ClickScheduler, make_click
from dino_shred.rhythm.conductor import Conductor


def test_make_click_shape_and_decay() -> None:
    click = make_click(sr=48000, dur_ms=5.0, amp=0.5)
    assert click.dtype == np.float32
    assert len(click) == 240  # 5 ms at 48 kHz
    assert np.abs(click).max() <= 0.5 + 1e-6
    assert np.abs(click[-10:]).max() < np.abs(click[:10]).max()  # decays


def test_click_lands_at_exact_sample_offset() -> None:
    c = Conductor(t0=1.0, bpm=120.0)  # beats at 1.0, 1.5, 2.0 ...
    s = ClickScheduler(c, sr=48000)
    out = np.zeros(48000, dtype=np.float32)  # covers [0.5, 1.5)
    s.render(dac_time=0.5, out=out)
    onset = int(np.flatnonzero(out != 0.0)[0])
    assert onset == 24000  # (1.0 - 0.5) * 48000


def test_rendering_in_blocks_equals_one_shot() -> None:
    """A click spanning a buffer boundary must be identical to the unblocked render.

    t0=0.001 puts beats at sample 48 + k*19200, so the 240-sample click around
    beat 1 (samples 19248-19487) genuinely crosses the block edge at 19456.
    """
    sr = 48000
    n = 256 * 187  # exactly 187 blocks
    c = Conductor(t0=0.001, bpm=150.0)
    whole = np.zeros(n, dtype=np.float32)
    ClickScheduler(c, sr=sr).render(0.0, whole)

    s2 = ClickScheduler(c, sr=sr)
    blocks = []
    for i in range(0, n, 256):
        b = np.zeros(256, dtype=np.float32)
        s2.render(i / sr, b)
        blocks.append(b)
    np.testing.assert_allclose(np.concatenate(blocks), whole, atol=1e-7)


def test_bar_start_is_accented() -> None:
    c = Conductor(t0=0.0, bpm=60.0)
    s = ClickScheduler(c, sr=48000, beats_per_bar=4)
    beat0 = np.zeros(4800, dtype=np.float32)
    beat1 = np.zeros(4800, dtype=np.float32)
    s.render(0.0, beat0)  # beat 0 -> accent
    s.render(1.0, beat1)  # beat 1 -> normal
    assert np.abs(beat0).max() > np.abs(beat1).max()
