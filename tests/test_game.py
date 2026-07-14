import pygame

from dino_shred.audio.detect import OnsetEvent
from dino_shred.game.game import RhythmGame, State
from dino_shred.rhythm.judge import Grade


def ev(t: float) -> OnsetEvent:
    return OnsetEvent(t=t, strength=1.0, detector="test")


def start_game(bpm: float = 100.0) -> RhythmGame:
    g = RhythmGame(bpm=bpm)
    g.start_playing(t_now=50.0)
    assert g.conductor is not None
    assert g.judge is not None
    return g


def test_start_playing_creates_grid_with_lead_in_and_count_in() -> None:
    g = start_game()
    assert g.state is State.PLAYING
    assert g.conductor is not None
    assert g.conductor.t0 == 51.0  # 1 s lead-in
    assert g.judge is not None and g.judge.first_beat == 4  # count-in unjudged


def test_conductor_change_hook_fires() -> None:
    seen = []
    g = RhythmGame(bpm=100.0)
    g.on_conductor_change = seen.append
    g.start_playing(t_now=50.0)
    assert seen == [g.conductor]


def test_onset_jumps_and_judges() -> None:
    g = start_game()
    assert g.conductor is not None
    assert g.judge is not None
    beat5 = g.conductor.beat_time(5)
    g.update(beat5 - 0.5)
    g.handle_onset(ev(beat5))
    assert not g.dino.on_ground
    assert g.judge.counts[Grade.PERFECT] == 1


def test_missed_beats_counted_on_update() -> None:
    g = start_game()
    assert g.conductor is not None
    assert g.judge is not None
    g.update(g.conductor.beat_time(8))  # sail past beats 4..7 without chugging
    assert g.judge.counts[Grade.MISS] >= 3


def test_collision_with_grounded_dino_ends_game() -> None:
    g = start_game()
    assert g.conductor is not None
    # walk time up to the first spawned obstacle's beat; dino never jumps
    t = g.conductor.beat_time(4)
    for _ in range(120):
        g.update(t - 3.0 + _ * 0.025)  # 3 s approach in 25 ms steps
        if g.state is State.GAME_OVER:
            break
    assert g.state is State.GAME_OVER


def test_calibration_flow_produces_offset() -> None:
    g = RhythmGame(bpm=100.0)
    g.start_calibration(t_now=10.0)
    assert g.state is State.CALIBRATE
    assert g.conductor is not None
    for n in range(24):
        g.handle_onset(ev(g.conductor.beat_time(n) + 0.040))
        g.update(g.conductor.beat_time(n) + 0.1)
    assert g.calibration_result is not None
    offset, _spread = g.calibration_result
    assert abs(offset - 0.040) < 0.005
    assert g.state is State.MENU


def test_keyboard_space_acts_as_onset() -> None:
    g = start_game()
    assert g.conductor is not None
    g.handle_key(pygame.K_SPACE, down=True, t_now=g.conductor.beat_time(5))
    assert not g.dino.on_ground


def test_onset_on_menu_or_game_over_starts_game() -> None:
    # 1. On MENU state
    g = RhythmGame(bpm=100.0)
    assert g.state is State.MENU
    g.handle_onset(ev(10.0))
    assert g.state is State.PLAYING
    assert g.conductor is not None
    assert g.conductor.t0 == 11.0  # 1s lead-in

    # 2. On GAME_OVER state
    g.state = State.GAME_OVER
    g.handle_onset(ev(20.0))
    assert g.state is State.PLAYING
    assert g.conductor is not None
    assert g.conductor.t0 == 21.0

