"""The jump must fit between beats: air time is the design constant (ADR 0004)."""

from dino_shred import config


def test_air_time_is_shorter_than_slowest_beat_period() -> None:
    # V1 default is 80 BPM -> 750 ms period; air time must leave judging room.
    assert config.AIR_TIME_S <= 0.4


def test_discrete_jump_matches_derived_constants() -> None:
    """Simulate the per-frame physics exactly as Dino.update() will run them."""
    y, vy = 0.0, config.JUMP_VEL
    frames = 0
    peak = 0.0
    while True:
        vy += config.GRAVITY
        y += vy
        frames += 1
        peak = min(peak, y)
        if y >= 0.0:
            break
    assert abs(frames - config.AIR_TIME_S * config.FPS) <= 1.5
    assert abs(-peak - config.JUMP_HEIGHT_PX) <= config.JUMP_HEIGHT_PX * 0.15
