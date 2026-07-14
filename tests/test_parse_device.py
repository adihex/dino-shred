import pytest
from dino_shred.audio.engine import parse_device

def test_parse_device() -> None:
    assert parse_device(None) is None
    assert parse_device("1") == 1
    assert parse_device("1,0") == (1, 0)
    assert parse_device("USB AUDIO  CODEC") == "USB AUDIO  CODEC"
