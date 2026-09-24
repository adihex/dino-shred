from dino_shred import config
from dino_shred.game.objects import Dino


def test_dino_jump_and_land_cycle() -> None:
    d = Dino()
    assert d.on_ground
    d.jump()
    assert not d.on_ground and d.vy == config.JUMP_VEL
    for _ in range(int(config.AIR_TIME_S * config.FPS) + 3):
        d.update()
    assert d.on_ground and d.vy == 0


def test_no_double_jump_midair() -> None:
    d = Dino()
    d.jump()
    d.update()
    vy_before = d.vy
    d.jump()  # ignored while airborne
    assert d.vy == vy_before


def test_duck_shrinks_hitbox() -> None:
    d = Dino()
    standing = d.rect.height
    d.duck(True)
    assert d.rect.height < standing
