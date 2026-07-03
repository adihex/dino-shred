# Audio Stack Research — 2026-07-03

Four parallel research agents verified library viability **locally on this machine**
(macOS arm64, CPython 3.13.9, uv) plus primary-source documentation review.
This document is the distilled result; it grounds every stack decision in
`docs/decisions/`.

## 1. aubio (real-time onset detection library)

**Verdict: usable only as a git-pinned dev dependency; never from PyPI.**

- PyPI release 0.4.9 (Feb 2019, sdist-only, no wheels) **fails to compile** on
  Python 3.13 / numpy 2.x — verified locally (`ufuncs.c` C-API errors from numpy 2.0's
  const-ified ufunc signatures).
- Git master (`0.5.0a0`, commit `ad5cf975`) **builds and works** — verified locally:
  imports against numpy 2.4.6, all 10 onset methods (`energy`, `hfc`, `specflux`, …)
  detected synthetic 110 Hz guitar plucks at 48 kHz within ~10 ms of ground truth.
- Performance: **3.0 µs per 256-sample hop** (0.06 % CPU). Never the bottleneck.
- Maintenance: repo alive (commits Apr 2026) but no release in 7+ years. GPLv3+.
- Real-time API: `o = aubio.onset(method, buf_size, hop_size, sr)`; feed exactly
  `hop_size` float32 samples per call; nonzero return = onset in that hop;
  `get_last()` returns sample-accurate position **with delay compensation already
  subtracted** (default 4.3×hop ≈ 22.9 ms — beware when comparing timestamps).
- Defaults are wrong for DI guitar: raise `silence` −70→≈−48 dB, `threshold`
  0.06→0.1–0.3, `minioi_ms` ≈ 80 to debounce pick attacks.

## 2. sounddevice / PortAudio (audio transport)

**Verdict: the transport layer. No contest.**

- v0.5.5 (Jan 2026, actively maintained) installs clean on 3.13/arm64 — universal2
  wheel **bundles PortAudio** (V19.7.0-devel), zero system deps. Verified locally.
- PyAudio comparison: last release Nov 2023, no macOS wheels, **failed to build
  locally** (missing `portaudio.h`). Dead end.
- Callback API gives hardware timestamps: `time.inputBufferAdcTime` (when sample 0
  physically hit the ADC) and `time.outputBufferDacTime` (when sample 0 will leave
  the DAC) — the foundation of all our timing (see `docs/learning/01-the-audio-clock.md`).
- **Verified locally:** two simultaneous PortAudio streams *and* `time.monotonic()`
  agree to ~2–7 µs on this Mac (mach host clock). Portability note: the PortAudio
  spec only guarantees the timebase per-stream — one duplex stream is the portable design.
- **macOS TCC mic-permission trap confirmed live:** `InputStream` open *hangs
  indefinitely* (no exception) without Microphone permission for the hosting
  terminal app. Other symptom: stream opens but delivers all-zero samples.
  First run must be from Terminal.app; grant in System Settings → Privacy & Security
  → Microphone. VS Code's integrated terminal historically fails to show the prompt.
- Latency: `latency='low'` matters (default gave 32 ms reported output latency;
  blocksize=128 @48 kHz = 2.67 ms/block was honored exactly). M-Track Solo published
  round-trip ≈ 9.4 ms at 64-sample buffers; input-only path ≈ 3–6 ms.
- Real-time callback discipline: no allocation, no locks, no I/O; exceptions are
  swallowed (stderr only) — needs a heartbeat watchdog. Duplex `outdata` is
  uninitialized memory — must be filled every callback.
- Callbacks fire in bursts at stream start (verified: 4 back-to-back with identical
  `currentTime`) — never count callbacks; always schedule against `outputBufferDacTime`.
- `sd.CoreAudioSettings(change_device_parameters=True)` can lower the device's
  hardware buffer for genuinely lower latency.

## 3. Offline beat tracking (V2 level generation)

**Verdict: `beat_this` for extraction, `librosa` for decoding + the learning baseline.**

All verified with real installs + functional runs on a synthetic 137 BPM click track:

| Library | Installs on 3.13/arm64? | Result on 137 BPM test | Notes |
|---|---|---|---|
| librosa 0.11.0 | ✅ | 136.0 BPM, 67 beats | maintained; ~33 s numba JIT warm-up on first call |
| beat_this 1.1.0 | ✅ (pulls torch 2.12, 481 MB venv) | 136.4 BPM, beats **and downbeats**, 0.7 s wall/30 s audio | ISMIR 2024; GTZAN F1 89.1 beat / 78.3 downbeat — best published |
| essentia 2.1b6.dev1389 | ✅ (arm64 wheels now exist) | 136.99 BPM, confidence 3.84/5.32 | dev-tagged builds only; no downbeats |
| madmom 0.16.1 (PyPI) | ❌ verified failure | — | dead since 2018; git main works with workarounds but pointless |

- MP3 decoding needs **no extra setup**: soundfile's bundled libsndfile decodes MP3
  natively now (verified). ffmpeg 8.0.1 already installed for fallback formats.
- beat_this gotchas: 77 MB checkpoint auto-downloaded on first run (cache it);
  `dbn=True` requires madmom — avoid (paper says `dbn=False` is more accurate anyway);
  downbeat output is only meaningful on real music.
- All trackers can octave-fold tempo on double-kick metal (68.5 vs 137 BPM) —
  sanity-fold BPM into 70–180 via median inter-beat interval.
- **Torch must not enter the game environment** (481 MB) — level generation is a
  separate uv dependency group / tool.

## 4. Rhythm-game timing architecture

**Verdict: conductor pattern anchored to the PortAudio stream clock.**

- Canonical sources (fizzd/Rhythm Doctor guide, Rhythm Quest devlog): song position
  must derive from the **audio clock**, never wall clock or frame counts; never
  re-anchor timing references per frame.
- `pygame.mixer` is disqualified for the metronome click: no schedule-at-time API,
  sounds start on buffer boundaries (512 samples ≈ 10.7 ms quantization), no
  playback timestamps, clock uncorrelated with the input stream. Fine for menu
  bleeps only.
- Click scheduling instead: mix the click waveform into the duplex callback's output
  buffer at sample offset `round((beat_time(n) − outputBufferDacTime) × sr)` —
  sample-accurate, drift-free, self-compensating for output latency.
- Judgment windows across shipped games (half-widths): DDR Perfect ±33 ms /
  Marvelous ±16.7 ms; osu! OD8 ≈ ±32/±76/±120 ms; Clone Hero (a guitar game!)
  total window ±70 ms. **Chosen starting point: Perfect ±30 / Good ±60 / OK ±100 ms.**
- Calibration (Clone Hero model): play clicks, player strums along N times, offset =
  median(onset − beat) with outlier rejection, persisted and subtracted from every
  judged hit. Re-run when blocksize / samplerate / detector / interface changes.
- pygame 2.6 vsync: only honored with `SCALED`/`OPENGL` flags, experimental;
  `flip()` may block up to a frame — one more reason scoring never touches frame time.
- Because judging uses ADC/DAC hardware timestamps, output and display latency are
  **out of the scoring path entirely** — only detection delay and the player remain,
  which is exactly what calibration measures.

## Latency budget (end to end, verified numbers)

```
string hit → ADC + USB (M-Track)      ~3–6 ms
one 256-sample capture block           5.3 ms
detection confirmation (1–2 hops)      5–11 ms
processing                             ~1–2 ms
                                      ─────────
string → judged                       ~15–25 ms   (budget: 40 ms ✅)
```

Visual response adds a frame (≈16 ms) but is cosmetic — scoring doesn't see it.
