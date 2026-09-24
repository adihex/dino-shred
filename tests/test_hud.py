from dino_shred.game.hud import error_bar_x, format_error, histogram_bins


def test_format_error_signs_and_miss() -> None:
    assert format_error(-0.032) == "-32 ms early"
    assert format_error(0.045) == "+45 ms late"
    assert format_error(0.0) == "+0 ms late"
    assert format_error(None) == "MISS"


def test_error_bar_maps_range_to_pixels() -> None:
    assert error_bar_x(0.0, width=200) == 100  # centered
    assert error_bar_x(-0.1, width=200) == 0  # full early
    assert error_bar_x(0.1, width=200) == 200  # full late
    assert error_bar_x(0.5, width=200) == 200  # clamped


def test_histogram_bins_count_and_clip() -> None:
    bins = histogram_bins([-0.09, -0.01, 0.0, 0.01, 0.09, 0.3], n_bins=4, range_s=0.1)
    assert len(bins) == 4
    assert sum(bins) == 6  # out-of-range clipped into edge bins
    assert bins[1] + bins[2] == 3  # the three near-zero errors sit centrally
