from dino_shred.rhythm.conductor import Conductor


def test_beat_times_at_100_bpm() -> None:
    c = Conductor(t0=100.0, bpm=100.0)
    assert c.period == 0.6
    assert c.beat_time(0) == 100.0
    assert c.beat_time(5) == 103.0


def test_nearest_beat_rounds_correctly() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    assert c.nearest_beat(0.29) == 0
    assert c.nearest_beat(0.31) == 1
    assert c.nearest_beat(2.95) == 5
    assert c.nearest_beat(-0.2) == 0


def test_beats_in_window_half_open() -> None:
    c = Conductor(t0=10.0, bpm=120.0)  # period 0.5
    assert list(c.beats_in(10.0, 11.0)) == [0, 1]  # 11.0 excluded
    assert list(c.beats_in(10.9, 11.6)) == [2, 3]
    assert list(c.beats_in(10.2, 10.4)) == []
