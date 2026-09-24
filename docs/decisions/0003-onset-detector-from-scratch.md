# ADR 0003: Onset detection built from scratch in numpy; aubio as dev-only referee

**Date:** 2026-07-03 · **Status:** accepted

## Context

Detecting the guitar hit is the DSP heart of the project, and the project's primary
goal is *learning* signal processing. Options ranged from "use a library" to "build
everything".

## Decision

Build the detector **from scratch in numpy**, in three staged milestones — each one
a notebook chapter using recordings of the user's actual guitar:

1. **`EnergyGate`** (time domain): per-hop RMS in dB, rising-edge threshold with
   hysteresis, ~80 ms refractory period. Gets the game playable fast and teaches
   envelopes, gating, and why naive detectors double-trigger.
2. **`SpectralFlux`** (frequency domain): Hann-windowed rFFT per hop, half-wave-
   rectified magnitude increase summed across bins, adaptive threshold
   (rolling median + k·MAD), peak picking, refractory. The real, robust detector.
3. **`ChugClassifier`**: on each onset, low-band (≈60–250 Hz) vs full-band energy
   ratio + spectral decay shape to distinguish palm-muted chugs from open notes.

All three implement one protocol —
`process(frame: np.float32[hop], t_frame: float) -> OnsetEvent | None` —
so the game can swap detectors via a CLI flag.

**aubio** (git-pinned to commit `ad5cf975`, since PyPI 0.4.9 is broken on
Python 3.13 — verified) is a **dev-dependency only**, used in notebooks/tests as a
reference implementation: our detector's precision/recall is benchmarked against
aubio's 10 methods on labeled recordings. It never ships in the game path.

## Alternatives considered

- **aubio in the game** — fastest to reliable gameplay (verified working, 3 µs/hop),
  but reduces the learning to threshold-tuning; also an unreleased GPL alpha pinned
  from git as a runtime dependency.
- **aubio first, replace later** — two integrations, and "later" plausibly never
  comes once the game works.
- **madmom / essentia streaming** — unmaintained (2018) / heavyweight C++ dep
  respectively; both rejected.

## Consequences

- One or two extra days before detection feels solid, spent exactly where the
  learning is.
- The refactor must define the detector protocol early so game code is
  detector-agnostic.
- Test fixtures: real chug recordings with hand-labeled onset times live in
  `assets/recordings/` and gate regressions in CI/pytest.
- Detector group delay (window centering + hop granularity) is a near-constant,
  absorbed by the calibration offset (ADR 0004) — but must be documented per
  detector so calibration is re-run when the detector changes.
