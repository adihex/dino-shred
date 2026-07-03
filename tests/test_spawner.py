import pytest

from dino_shred import config
from dino_shred.game.objects import Dino, Obstacle
from dino_shred.game.spawner import Spawner
from dino_shred.rhythm.conductor import Conductor


def test_obstacle_centered_on_dino_exactly_at_its_beat() -> None:
    c = Conductor(t0=50.0, bpm=100.0)
    obs = Obstacle(beat_n=8, conductor=c, variant=0)
    beat_t = c.beat_time(8)
    assert obs.rect(beat_t).centerx == Dino().rect.centerx


def test_obstacle_moves_left_at_px_per_sec() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    obs = Obstacle(beat_n=4, conductor=c, variant=1)
    assert obs.x(1.0) - obs.x(1.5) == pytest.approx(0.5 * config.PX_PER_SEC)


def test_obstacle_is_gone_after_leaving_screen() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    obs = Obstacle(beat_n=0, conductor=c, variant=0)
    assert not obs.is_gone(c.beat_time(0))
    assert obs.is_gone(c.beat_time(0) + 2.0)  # long gone left of the screen


def test_spawner_every_4th_beat_early_no_duplicates() -> None:
    c = Conductor(t0=10.0, bpm=120.0)  # period 0.5: beat n at 10.0 + n*0.5
    s = Spawner(c, first_beat=4, horizon_s=3.0, seed=7)
    first = s.update(t=10.0)  # horizon < 13.0 covers beats 4,5 -> eligible: 4
    assert [o.beat_n for o in first] == [4]
    assert s.update(t=10.0) == []  # idempotent: nothing new until time advances
    later = s.update(t=11.1)  # horizon < 14.1 adds beats 6,7,8 -> eligible: 8
    assert [o.beat_n for o in later] == [8]
    assert all(o.variant in (0, 1) for o in first + later)


def test_density_ramps_4_2_1() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    s = Spawner(c, first_beat=4)
    assert s.density(4) == 4  # first 16 beats: every 4th
    assert s.density(4 + 16) == 2  # next stretch: every 2nd
    assert s.density(4 + 48) == 1  # then every beat
