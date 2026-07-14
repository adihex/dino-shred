"""Hardware smoke test: click plays, you chug, errors print. Run before the game.

    uv run python -m dino_shred.audio.check --bpm 100

First run on macOS: run from Terminal.app so the Microphone permission prompt
appears (see docs/research/2026-07-03-audio-stack-research.md, TCC section).
"""

import argparse
import statistics
import time

import sounddevice as sd

from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate
from dino_shred.audio.engine import AudioEngine, DeviceNotFoundError, find_device
from dino_shred.rhythm.conductor import Conductor


def format_hit(onset_t: float, conductor: Conductor) -> str:
    n = conductor.nearest_beat(onset_t)
    err_ms = (onset_t - conductor.beat_time(n)) * 1000.0
    side = "early" if err_ms < 0 else "late"
    return f"beat {n}  {err_ms:+.1f} ms {side}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bpm", type=float, default=100.0)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--input-channel", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--list", action="store_true", help="list devices and exit")
    args = parser.parse_args()

    if args.list:
        print(sd.query_devices())
        return

    from dino_shred.audio.engine import parse_device

    device_arg = parse_device(args.device)
    try:
        if isinstance(device_arg, str) or device_arg is None:
            name = device_arg if device_arg is not None else "M-Track"
            device = find_device(name)
        else:
            device = device_arg
    except DeviceNotFoundError as e:
        raise SystemExit(str(e)) from e

    # Bootstrap: engine needs a scheduler, scheduler needs t0 from the engine's
    # clock. Start with scheduler=None, then attach once the stream is running.
    engine = AudioEngine(
        detector=EnergyGate(),
        scheduler=None,
        device=device,
        input_channel=args.input_channel,
    )
    engine.start()
    conductor = Conductor(t0=engine.time + 1.0, bpm=args.bpm)
    engine.scheduler = ClickScheduler(conductor)

    print(f"Clicking at {args.bpm:g} BPM for {args.seconds:g}s - chug along! Ctrl-C stops.")
    errors: list[float] = []
    silent_since: float | None = time.monotonic()
    try:
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            time.sleep(0.05)
            for ev in engine.get_events():
                errors.append(ev.t - conductor.beat_time(conductor.nearest_beat(ev.t)))
                print(format_hit(ev.t, conductor))
            if engine.take_peak() > 1e-4:
                silent_since = None
            elif silent_since is not None and time.monotonic() - silent_since > 3.0:
                print(
                    "!! No input signal for 3s. Check: guitar in input 2, gain up,\n"
                    "!! and macOS Microphone permission for your terminal\n"
                    "!! (System Settings > Privacy & Security > Microphone)."
                )
                silent_since = time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()

    if errors:
        med = statistics.median(errors) * 1000.0
        print(
            f"\n{len(errors)} hits, median error {med:+.1f} ms "
            f"(xruns={engine.status.xruns}, drops={engine.status.queue_drops})"
        )
    else:
        print("\nNo hits detected.")


if __name__ == "__main__":
    main()
