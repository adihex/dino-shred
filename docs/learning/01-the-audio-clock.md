# Learning note 01 — The Audio Clock

*The single most important concept in this project. Everything else is bookkeeping.*
*(Notebook chapter 04 will have you measure all of this on your own rig.)*

## The problem: three clocks, all lying differently

| Clock | Who owns it | Problem |
|---|---|---|
| **Frame clock** | pygame's loop (`clock.tick(60)`) | "60 fps" is a lie — frames take 15.8 ms, 17.2 ms, sometimes 33 ms when `flip()` blocks on vsync. Count 36 frames as "600 ms" and a metronome audibly wanders within a minute. |
| **Wall clock** | `time.monotonic()` in Python | Accurate about *now*, but Python never observes audio events *when they happen* — only when the OS schedules it to look. |
| **Audio hardware clock** | the M-Track's crystal, ticking 48 000 samples/sec | Knows nothing about your code — but it is the clock the *sound itself* rides on. |

The killer subtlety is the middle row. Suppose you chug at physical time **T**:

```
string hit ─► ADC converts ─► USB packet ─► CoreAudio buffer ─► Python callback runs
     T            T+~1ms         T+~3ms         T+~5ms            T+5–15ms  (jittery!)
```

Timestamp the onset with `time.monotonic()` *when your code notices it* and you've
measured "when Python got scheduled" — smeared by ±5–10 ms of OS scheduling noise.
Our Perfect window is **±30 ms**; the ruler itself would wobble a third of the window.
Same story in reverse for the click: `play()` returns immediately but sound leaves
the DAC 10–40 ms later, and `pygame.mixer` will never tell you when.

## The fix: the hardware timestamps its own samples

Audio moves in blocks (256 samples = 5.33 ms at 48 kHz). Each time PortAudio calls
our callback it passes `time_info`, containing two hardware-referenced facts:

- **`inputBufferAdcTime`** — "sample 0 of this input block physically entered the
  ADC at stream-time X"
- **`outputBufferDacTime`** — "sample 0 of the output block you are about to fill
  will physically leave the DAC at stream-time Y"

Samples tick at exactly 48 kHz on that clock, so **sample k = time X + k/48000**.
You now have microsecond-grade labels on physical events — and *it no longer matters
when Python runs*.

## One beat, end to end (100 BPM → a beat every 600 ms)

Song started at `t0 = 100.000` stream-seconds. Beat 5 is due at
`beat_time(5) = 100.000 + 5×0.600 = 103.000`.

**Click out.** A callback reports `outputBufferDacTime = 102.9980`; its block covers
`[102.9980, 103.0033)`. Beat 103.000 falls inside. Offset =
`(103.000 − 102.9980) × 48000 = 96`. We copy the click waveform into the output
buffer starting at **sample 96**. It leaves the DAC at 103.000000 — not "roughly
when we called play()", but exactly on the grid, every time, with zero drift.

**Chug in.** You hit the strings. Some later callback reports
`inputBufferAdcTime = 102.9950`; the detector finds the onset at sample 240:

```
onset_t = 102.9950 + 240/48000 = 103.0000
```

**Judgment.** `error = onset_t − beat_time(5) = 0.0` → **PERFECT** — even though
Python didn't process that buffer until stream-time ≈103.008. The *processing* was
8 ms late; the *label* was exact. That's the whole trick: stop asking "when did the
code run", ask "when did the sound exist".

```
stream time ────102.4────────103.0────────103.6──────►
beat grid          ♪    beat5→ ♪            ♪
click DAC out ─────────────────█  (scheduled at sample offset — exact)
chug ADC in ───────────────────█  (timestamped by hardware — exact)
python actually ran ───────────────↑  (late, jittery — and irrelevant)
```

## Why ONE duplex stream

Clicks out the MacBook speakers + guitar in the M-Track = **two crystals** each
claiming "48 000 Hz". Real crystals disagree by a few ppm → the two timelines drift
~1 ms/minute, and each side has a separate unknown latency. One full-duplex stream
on the M-Track = one crystal stamps both directions, and PortAudio guarantees both
timestamps share a timebase. (Monitor through the M-Track's headphone jack; its
direct-monitor knob mixes your dry guitar in at zero latency, in hardware.)

Measured on this Mac: PortAudio stream time and `time.monotonic()` agree to ~5 µs —
so the pygame thread can cheaply ask "what stream-time is it now?" to draw obstacles.
But scoring never depends on that; it derives purely from ADC/DAC stamps.

## The Conductor is just… this, wrapped

```python
class Conductor:
    def beat_time(self, n): return self.t0 + n * (60 / self.bpm)     # the grid
    def nearest_beat(self, t): return round((t - self.t0) / (60 / self.bpm))
    def now(self): return self.stream.time                            # rendering only
```

Nothing is ever *advanced* or *accumulated* — click offsets, obstacle positions,
judgment errors are all **derived fresh from the clock** each time they're needed.
No integration ⇒ no accumulated error ⇒ nothing can drift.

What's left over — the detector reporting an onset a few ms after the pick attack
begins, plus your own anticipation bias — is a near-**constant**. Constants can be
measured once and subtracted: that's exactly what the calibration screen does
(median of ~20 strums against the click).

## Further reading

- fizzd (Rhythm Doctor): *How to make a rhythm game — a quick and dirty guide*
- Rhythm Quest devlog #4: audio-clock smoothing for rendering
- PortAudio docs: `PaStreamCallbackTimeInfo`
- `docs/research/2026-07-03-audio-stack-research.md` — verified numbers for this rig
