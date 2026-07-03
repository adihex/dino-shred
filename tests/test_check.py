from dino_shred.audio.check import format_hit
from dino_shred.rhythm.conductor import Conductor


def test_format_hit_reports_signed_error() -> None:
    c = Conductor(t0=100.0, bpm=100.0)
    assert "early" in format_hit(102.98, c) and "-20.0 ms" in format_hit(102.98, c)
    assert "late" in format_hit(103.03, c) and "+30.0 ms" in format_hit(103.03, c)
    assert "beat 5" in format_hit(102.98, c).replace("  ", " ")
