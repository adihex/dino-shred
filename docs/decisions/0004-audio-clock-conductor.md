# ADR 0004: All timing on the audio stream clock (conductor pattern); time-derived motion

**Date:** 2026-07-03 · **Status:** accepted

## Context

The game must know, to a few milliseconds, when a click sounded and when a chug
happened — but Python observes audio only in buffered, jittery callbacks, and pygame
frames are irregular (vsync `flip()` can block a full frame). Rhythm games solved
this decades ago: the *conductor pattern* — one authoritative music clock that
everything else derives from. Full explanation with a worked example:
`docs/learning/01-the-audio-clock.md`.

## Decision

1. **The beat grid lives on the PortAudio stream clock.**
   `beat_time(n) = t0 + n · 60/bpm`, in stream-time seconds. The `Conductor` object
   owns `t0`/`bpm` and answers `beat_time(n)`, `nearest_beat(t)`, `now()`.
   Nothing is ever advanced incrementally; every quantity is derived fresh from the
   clock, so there is no accumulated error and nothing to drift.
2. **Scoring uses hardware timestamps only.** Onset time comes from
   `inputBufferAdcTime + sample/sr`; click time is scheduled against
   `outputBufferDacTime`. Output latency and display latency thereby cancel out of
   the scoring path entirely.
3. **Obstacles are positioned from time, not integrated.** Instead of
   `x -= speed` per frame, an obstacle bound to beat *n* computes
   `x(t) = dino_x + (beat_time(n) − t) · px_per_sec` each frame — it arrives at the
   dino exactly on its beat regardless of frame jitter.
4. **Judgment** = `error = onset_t − calibration_offset − beat_time(nearest)`,
   graded Perfect ±30 ms / Good ±60 ms / OK ±100 ms / Miss (informed by DDR, osu!,
   Clone Hero windows; tightened later). One onset consumes at most one beat;
   off-grid extra onsets still make the dino jump but don't score.
5. **Calibration** absorbs the leftover near-constants (detector group delay +
   player bias): click at ~100 BPM, ≥20 chugs, drop the first 4, offset =
   median(error) with MAD outlier rejection, persisted to a local config with the
   device/detector/blocksize it was measured under.

## Alternatives considered

- **Frame-count or wall-clock scheduling** — rejected: measured frame jitter and
  buffer latency are the same order as the judgment windows; the metronome would
  audibly wander within a minute.
- **`time.monotonic()` bridging between separate input/output streams** — works on
  macOS (verified: PortAudio stream time ≡ mach host clock to ~5 µs) but is an
  implementation detail, not a PortAudio guarantee; single duplex stream is the
  portable design (ADR 0002).

## Consequences

- V1→V2 hinge: V2 constructs the `Conductor` from an extracted `beats[]` array
  (`np.searchsorted` for `nearest_beat`) instead of a fixed BPM — game code
  unchanged.
- Jump physics must be re-tuned: current air time (~583 ms) nearly equals the beat
  period at 100 BPM (600 ms). Air time becomes a derived constant (~300–350 ms)
  and/or V1 starts at lower BPM.
- The renderer may read `now()` per frame; if visuals ever stutter, smoothing
  (rolling linear fit, monotonic clamp) applies to the *displayed* position only —
  never to judged timestamps.
