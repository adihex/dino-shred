# ADR 0002: One full-duplex sounddevice stream; pygame.mixer banned from the timing path

**Date:** 2026-07-03 · **Status:** accepted

## Context

The game needs (a) low-latency guitar capture with precise onset timestamps and
(b) a metronome click whose exact playback time is known — both referenced to one
clock so `onset − beat` is meaningful at ±30 ms judgment windows.

## Decision

Use **python-sounddevice 0.5.5** as the *only* audio I/O layer, with **one
full-duplex `sd.Stream`** on the M-Track Solo (guitar in, click out):

```python
sd.Stream(device=(mtrack, mtrack), samplerate=48000, blocksize=256,
          dtype="float32", channels=(2, 2), latency="low", callback=cb)
# capture BOTH input columns and select the instrument one — on the M-Track Solo
# ch1 is the XLR/mic combo, ch2 is the Hi-Z instrument input (default column 1)
```

- Onsets are timestamped `time.inputBufferAdcTime + sample_index/48000`.
- Clicks are mixed into `outdata` at sample offset
  `round((beat_time(n) − time.outputBufferDacTime) × 48000)`.
- One device = one crystal = zero drift between the two directions; PortAudio
  guarantees a shared timebase per stream.
- The player monitors via the M-Track headphone jack (its hardware direct-monitor
  knob provides zero-latency self-monitoring of the guitar).
- `pygame.mixer` is **never initialized**. Pygame renders; it does not touch audio.

## Alternatives considered

- **pygame.mixer for the click** — rejected: no schedule-at-time API, ~10.7 ms
  buffer-boundary quantization, no playback timestamps, and its output clock is
  uncorrelated with the input stream. Timing feedback would be smeared beyond the
  judgment windows.
- **PyAudio** — rejected: last release Nov 2023, no macOS wheels, failed to build
  locally on Python 3.13; same PortAudio underneath with a worse API.
- **Separate input and output streams / separate devices** (e.g. clicks through
  MacBook speakers) — rejected: two clocks that drift a few ppm apart, aggregate-
  device resampling pitfalls, speaker-to-ear acoustic delay.

## Consequences

- Real-time callback discipline everywhere: preallocated buffers, no locks/allocation/
  I/O in the callback, `outdata` fully written every call, events cross to the game
  thread via a bounded queue.
- Exceptions in the callback are swallowed by PortAudio → we need a heartbeat
  watchdog so dead audio is detected and surfaced.
- macOS TCC: first run must happen from a terminal app with Microphone permission,
  or the stream hangs/delivers zeros (verified). The engine ships a silence watchdog
  with an actionable error message.
- Verified locally: this design yields ~15–25 ms string-to-judgment latency, inside
  the 40 ms budget (`docs/research/2026-07-03-audio-stack-research.md`).
