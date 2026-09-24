"""Composition root: engine + game + pygame loop. pygame.mixer is NEVER
initialized (ADR 0002) — pygame.display/font only.
"""

import argparse
import time
from datetime import date

import pygame

from dino_shred import config
from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate
from dino_shred.audio.engine import AudioEngine, DeviceNotFoundError
from dino_shred.game.game import RhythmGame


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dino-shred", description="Guitar-controlled rhythm trainer")
    p.add_argument("--bpm", type=float, default=80.0)
    p.add_argument(
        "--device", type=str, default=None, help="sounddevice index or name/pair (default: find M-Track)"
    )
    p.add_argument(
        "--input-channel",
        type=int,
        default=2,
        help="1-based input channel (M-Track instrument = 2)",
    )
    p.add_argument("--keyboard-only", action="store_true", help="no audio: SPACE jumps")
    p.add_argument("--debug-hud", action="store_true", help="show xruns/drops/latency")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    engine: AudioEngine | None = None
    if not args.keyboard_only:
        from dino_shred.audio.engine import find_device, parse_device

        try:
            device_arg = parse_device(args.device)
            if isinstance(device_arg, str) or device_arg is None:
                name = device_arg if device_arg is not None else "M-Track"
                resolved_device = find_device(name)
            else:
                resolved_device = device_arg

            engine = AudioEngine(
                detector=EnergyGate(),
                scheduler=None,
                device=resolved_device,
                input_channel=args.input_channel,
            )
            engine.start()
        except DeviceNotFoundError as e:
            raise SystemExit(f"{e}\n(Or run with --keyboard-only.)") from e

    clock_now = (lambda: engine.time) if engine is not None else time.monotonic

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
    pygame.display.set_caption("Dino Shred - guitar mode" if engine else "Dino Shred - keyboard")
    frame_clock = pygame.time.Clock()

    calibration = config.load_calibration()
    offset = 0.0
    game = RhythmGame(bpm=args.bpm)
    if calibration is not None and engine is not None:
        if calibration.is_stale("M-Track Solo", "energy", config.BLOCKSIZE):
            game.banner = "calibration is stale (setup changed) - press C to recalibrate"
        else:
            offset = calibration.offset_s
    elif engine is not None:
        game.banner = "not calibrated - press C on the menu"
    game.offset_s = offset

    if engine is not None:
        game.on_conductor_change = lambda c: setattr(engine, "scheduler", ClickScheduler(c))

    last_watchdog = 0.0
    silent_for = 0.0
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type in (pygame.KEYDOWN, pygame.KEYUP):
                    game.handle_key(event.key, event.type == pygame.KEYDOWN, clock_now())

            if engine is not None:
                for ev in engine.get_events():
                    game.handle_onset(ev)

            if game.calibration_result is not None:  # persist a finished calibration
                offset_s, spread_s = game.calibration_result
                config.save_calibration(
                    config.CalibrationData(
                        offset_s=offset_s,
                        spread_s=spread_s,
                        date=date.today().isoformat(),
                        device="M-Track Solo",
                        detector="energy",
                        blocksize=config.BLOCKSIZE,
                    )
                )
                game.calibration_result = None
                game.banner = (
                    f"calibrated: {offset_s * 1000:+.0f} ms (spread {spread_s * 1000:.0f} ms)"
                )

            if engine is not None:
                now = time.monotonic()
                if now - last_watchdog >= 1.0:  # 1 Hz watchdog poll
                    last_watchdog = now
                    silent_for = 0.0 if engine.take_peak() > 1e-4 else silent_for + 1.0
                    if silent_for >= 3.0:
                        game.banner = "no input signal - check gain + macOS Microphone permission"
                    elif game.banner.startswith("no input"):
                        game.banner = ""
                    if abs(engine.time - engine.status.last_callback_time) > 0.5:
                        game.banner = "AUDIO DEAD - callback stopped (see stderr)"
                    if args.debug_hud:
                        s = engine.status
                        pygame.display.set_caption(
                            f"Dino Shred  xruns={s.xruns} drops={s.queue_drops}"
                        )

            t = clock_now()
            game.update(t)
            game.draw(screen, t)
            pygame.display.flip()
            frame_clock.tick(config.FPS)
    finally:
        if engine is not None:
            engine.stop()
        pygame.quit()
