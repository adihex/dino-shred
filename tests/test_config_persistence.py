from pathlib import Path

from dino_shred.config import CalibrationData, load_calibration, save_calibration


def make_data() -> CalibrationData:
    return CalibrationData(
        offset_s=0.032,
        spread_s=0.008,
        date="2026-07-03",
        device="M-Track Solo",
        detector="energy",
        blocksize=256,
    )


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    save_calibration(make_data(), p)
    assert load_calibration(p) == make_data()


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_calibration(tmp_path / "absent.json") is None


def test_corrupt_file_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text("{not json")
    assert load_calibration(p) is None


def test_staleness_on_any_mismatch() -> None:
    d = make_data()
    assert not d.is_stale("M-Track Solo", "energy", 256)
    assert d.is_stale("M-Track Solo", "flux", 256)  # detector changed
    assert d.is_stale("M-Track Solo", "energy", 128)  # blocksize changed
    assert d.is_stale("Scarlett 2i2", "energy", 256)  # interface changed
