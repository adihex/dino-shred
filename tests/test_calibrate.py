import pytest

from dino_shred.rhythm.calibrate import CalibrationSession, compute_offset
from dino_shred.rhythm.conductor import Conductor


def test_compute_offset_median_and_spread() -> None:
    offset, spread = compute_offset([0.040, 0.045, 0.050, 0.055, 0.060])
    assert offset == pytest.approx(0.050)
    assert spread == pytest.approx(0.005)


def test_outliers_rejected_by_mad() -> None:
    errors = [0.048, 0.050, 0.052, 0.049, 0.051, 0.450]  # one wild miss-hit
    offset, _ = compute_offset(errors)
    assert offset == pytest.approx(0.050, abs=0.002)


def test_identical_errors_no_zero_division() -> None:
    offset, spread = compute_offset([0.05, 0.05, 0.05])
    assert (offset, spread) == (0.05, 0.0)


def test_session_discards_warmup_and_completes() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    s = CalibrationSession(c, min_hits=20, discard=4)
    for n in range(24):
        s.add_onset(c.beat_time(n) + 0.030)  # consistently 30 ms late
        assert s.is_complete is (n >= 23)
    offset, spread = s.result()
    assert offset == pytest.approx(0.030)
    assert spread == pytest.approx(0.0, abs=1e-9)
