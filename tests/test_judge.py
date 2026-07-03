import pytest

from dino_shred.rhythm.conductor import Conductor
from dino_shred.rhythm.judge import Grade, Judge


def make_judge(**kw) -> Judge:
    return Judge(Conductor(t0=100.0, bpm=100.0), **kw)  # beats at 100.0, 100.6, ...


@pytest.mark.parametrize(
    ("err", "grade"),
    [
        (0.0, Grade.PERFECT),
        (-0.030, Grade.PERFECT),
        (0.031, Grade.GOOD),
        (-0.060, Grade.GOOD),
        (0.061, Grade.OK),
        (-0.100, Grade.OK),
    ],
)
def test_window_boundaries(err: float, grade: Grade) -> None:
    j = make_judge()
    assert j.judge_onset(100.6 + err).grade is grade


def test_far_offbeat_is_off_grid_and_keeps_streak() -> None:
    j = make_judge()
    j.judge_onset(100.6)
    assert j.streak == 1
    verdict = j.judge_onset(100.6 + 0.25)  # way off any beat
    assert verdict.grade is Grade.OFF_GRID
    assert j.streak == 1  # off-grid never touches score


def test_one_onset_per_beat() -> None:
    j = make_judge()
    assert j.judge_onset(100.59).grade is Grade.PERFECT
    assert j.judge_onset(100.62).grade is Grade.OFF_GRID  # beat 1 already consumed


def test_calibration_offset_is_subtracted() -> None:
    j = make_judge(offset_s=0.050)  # detector+player measured 50 ms late
    assert j.judge_onset(100.6 + 0.050).grade is Grade.PERFECT


def test_sweep_marks_misses_and_resets_streak() -> None:
    j = make_judge()
    j.judge_onset(100.6)  # hit beat 1
    # advance past beats 2 and 3 without onsets (+ margin 0.05 + window 0.1)
    misses = j.sweep_misses(now=101.8 + 0.16)
    assert [m.beat_n for m in misses] == [0, 2, 3]  # beat 0 also never hit
    assert all(m.grade is Grade.MISS for m in misses)
    assert j.streak == 0
    assert j.counts[Grade.MISS] == 3


def test_sweep_respects_margin_for_inflight_events() -> None:
    j = make_judge()
    # beat 1 window closes at 100.70; sweep margin keeps it claimable until 100.75,
    # so a sweep at 100.72 only expires beat 0 and a late event can still claim beat 1.
    assert [m.beat_n for m in j.sweep_misses(now=100.72)] == [0]
    assert j.judge_onset(100.68).grade is Grade.OK


def test_first_beat_skips_count_in() -> None:
    j = make_judge(first_beat=4)
    assert [m.beat_n for m in j.sweep_misses(now=103.0)] == [4]  # beats 0-3 ignored
    assert j.judge_onset(100.6).grade is Grade.OFF_GRID  # count-in beat not judged
