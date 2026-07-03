from dino_shred.game.app import build_parser


def test_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.bpm == 80.0
    assert args.input_channel == 2
    assert not args.keyboard_only


def test_flags_parse() -> None:
    args = build_parser().parse_args(
        ["--bpm", "100", "--device", "3", "--keyboard-only", "--debug-hud"]
    )
    assert (args.bpm, args.device, args.keyboard_only, args.debug_hud) == (100.0, 3, True, True)
