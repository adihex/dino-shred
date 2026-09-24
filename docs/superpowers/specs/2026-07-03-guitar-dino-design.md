# Design: Guitar-Controlled Dino Rhythm Trainer ("Dino Shred")

**Date:** 2026-07-03 · **Status:** APPROVED (design review 2026-07-03; Parts 1 and 2
accepted by the user in interactive review).

## 1. What we're building

The dino-shred Chrome-Dino clone becomes a rhythm trainer controlled by an electric
guitar. Each chug makes the dino jump. A fixed-BPM metronome (audible click + visual
pulse) drives the game; obstacles are spawned so they arrive at the dino **exactly on
beats**; every chug is judged against the beat grid (`−40 ms early`, streaks, session
stats). Surviving = keeping time. V2 extends this to levels generated from real songs.

This is a learning project: the DSP core is built from scratch, each concept becomes
a notebook chapter, and each architectural choice an ADR in `docs/decisions/`.

**Requirements provenance:** ADR 0001. **Verified research:** `docs/research/2026-07-03-audio-stack-research.md`.

### Constraints

- Hardware: M-Audio M-Track Solo (48 kHz), guitar DI into the Hi-Z input; player
  monitors via the M-Track headphone jack (hardware direct-monitor for the guitar).
- Python 3.13, uv-managed, this repo. Pygame renders; it never touches audio.
- Latency budget: ≤40 ms string-to-judgment (measured path: ~15–25 ms ✅).
- Torch/ML stays out of the game runtime (separate uv group, V2 only).
- Keyboard fallback (space = jump) so the game runs without the interface.

## 2. Architecture (Part 1 — approved)

### The one rule

**All timing lives on the audio stream's clock** (ADR 0004, explained in
`docs/learning/01-the-audio-clock.md`). One full-duplex `sounddevice` stream on the
M-Track carries guitar-in and click-out on one hardware clock (ADR 0002):

- Beat grid: `beat_time(n) = t0 + n · 60/bpm` (stream-time seconds)
- Clicks: mixed into the output callback at sample offsets computed from
  `outputBufferDacTime` — sample-accurate, drift-free
- Onsets: timestamped `inputBufferAdcTime + sample/sr` — accurate regardless of
  Python scheduling
- Judgment: `error = onset_t − calibration_offset − beat_time(nearest)`
- Output/display latency cancel out of scoring (hardware-referenced stamps on both sides)

### Threads and data flow

```
                   ┌──────────────────────────────────────────────┐
guitar ─► M-Track  │ PortAudio callback thread (real-time)        │
  ▲    ADC ──────► │ in:  frame ─► OnsetDetector ─► OnsetEvent(t) ─► bounded queue
  │                │ out: mix click where beat_time(n) falls          │
headphones ◄────── │      inside this DAC buffer                      │
 (click + direct   └──────────────────────────────────────────────┘   ▼
  monitor)         ┌──────────────────────────────────────────────┐  drain per frame
                   │ Game thread (pygame, 60 fps)                 │◄──┘
                   │ • Conductor.now() → song position            │
                   │ • onset event → dino.jump() + Judge.judge()  │
                   │ • obstacle x(t) DERIVED from beat time       │
                   └──────────────────────────────────────────────┘
```

- Detection runs **inside the audio callback** (verified: µs-scale per hop) with
  preallocated buffers; documented fallback = worker thread if xruns appear.
- Obstacles are **time-derived, not integrated**:
  `x(t) = dino_x + (beat_time(n) − t) · px_per_sec` (ADR 0004).
- **A detected hit always jumps** — even a mistimed one. (In default mode any onset
  jumps; in `--chugs-only` mode, only classified chugs do.) Physics (beat-aligned
  obstacle collision) punishes bad timing; the HUD shows the numeric truth. Two
  feedback loops, one cause.

### Package layout

```
dino-shred/
├── main.py                      # original keyboard tutorial game — preserved as-is
├── dino_shred/
│   ├── audio/
│   │   ├── engine.py            # AudioEngine: duplex stream, callback, watchdogs
│   │   ├── clicks.py            # click synthesis + sample-accurate scheduler
│   │   └── detect.py            # EnergyGate → SpectralFlux → ChugClassifier
│   ├── rhythm/
│   │   ├── conductor.py         # beat grid on the stream clock (BPM now, beats[] in V2)
│   │   ├── judge.py             # windows ±30/±60/±100 ms, streaks, stats
│   │   └── calibrate.py         # median-of-N-strums offset → config
│   ├── game/
│   │   ├── objects.py           # Dino, Ground, Obstacle (time-anchored)
│   │   ├── hud.py               # judgment popups, error bar, histogram
│   │   ├── game.py              # states: MENU → CALIBRATE → PLAYING → GAME_OVER
│   │   └── app.py               # wiring + CLI flags
│   └── levels/                  # V2: level JSON schema + reader
├── tools/levelgen/              # V2: mp3 → level.json (beat_this; separate uv group)
├── notebooks/                   # learning chapters (ch1 = existing dino_shred.ipynb)
├── docs/{decisions,learning,research}/
├── assets/recordings/           # recorded chugs → labeled detector fixtures
└── tests/
```

## 3. Components (Part 2)

### 3.1 `audio/engine.py — AudioEngine`

- Finds the M-Track by name substring (`"M-Track"`); on failure: clear error listing
  available devices; `--device` override; `--keyboard-only` skips audio entirely.
- Opens the duplex stream: `samplerate=48000, blocksize=256, dtype='float32',
  channels=(2, 2), latency='low'` (+`sd.CoreAudioSettings(change_device_parameters=True)`).
  **Input channel selection matters:** the M-Track Solo's ch1 is the XLR/mic combo and
  **ch2 is the instrument (Hi-Z) input** — we capture both columns and take the
  configured one (`--input-channel`, default 2 → column index 1). A mono open would
  silently grab the wrong (mic) channel.
- Callback responsibilities, in order: fill `outdata` (silence + scheduled clicks);
  run detector on the mono input hop; push `OnsetEvent`s to a bounded queue
  (drop-oldest + overflow counter); update heartbeat (last callback stream-time,
  xrun/status flags).
- Game-thread watchdogs: **silence** (max |input| ≈ 0 over first ~2 s → actionable
  mic-permission warning), **stale heartbeat** (→ "audio dead" banner), **xrun counter**
  (debug HUD).
- Dev helper: `record(path)` captures input to WAV for notebooks/fixtures.

### 3.2 `audio/clicks.py`

- `make_click(sr, freq=1000, dur_ms=5)`: sine burst × exponential decay, normalized;
  accented variant (higher pitch/louder) for bar starts (`beats_per_bar=4`).
- `ClickScheduler`: given the conductor and a callback's `(dacTime, frames)`, yields
  `(sample_offset, waveform_slice)` pairs; handles clicks spanning buffer boundaries
  (carry-over state). Pure numpy, preallocated.

### 3.3 `audio/detect.py` (ADR 0003)

- `OnsetEvent(t: float, strength: float, detector: str)`.
- Common protocol: `process(frame: np.float32[hop], t_frame: float) -> OnsetEvent | None`;
  all state preallocated; selectable via `--detector energy|flux`.
- **`EnergyGate`** (M2): per-hop RMS→dB, rising-edge threshold + hysteresis,
  ~80 ms refractory.
- **`SpectralFlux`** (M4): Hann window over 512-sample frame (2 hops), rFFT,
  half-wave-rectified magnitude increase summed over bins, adaptive threshold
  (rolling median + k·MAD), peak pick, refractory; onset time interpolated within
  the hop. Group delay documented and absorbed by calibration.
- **`ChugClassifier`** (M5): wraps a detector; on onset computes low-band
  (≈60–250 Hz)/full-band energy ratio + decay shape → `kind: chug|note`; game mode
  "chugs only" uses it.

### 3.4 `rhythm/conductor.py`

- V1: `Conductor(t0, bpm)` — `beat_time(n)`, `nearest_beat(t)`, `now()`,
  `beats_in(t_start, t_end)` (for scheduler + renderer + spawner).
- V2: `Conductor.from_level(level)` — same interface over a `beats[]` array
  (`np.searchsorted`). Game code unchanged.
- `t0 = stream.time + lead_in` chosen at song start (count-in of 4 clicks).

### 3.5 `rhythm/judge.py`

- Windows (half-widths): **Perfect ±30 ms · Good ±60 ms · OK ±100 ms · else Miss**;
  constants, tightenable later ("precision mode").
- `judge(onset_t) → Judgment(beat_n, error_ms, grade)`; subtracts calibration offset.
- One onset consumes at most one beat; extra off-grid onsets → `OFF_GRID`
  (dino still jumps; no score effect).
- Beats with no onset by `beat_time + max_window` → Miss. **Game rule (explicit):**
  the player is expected to chug on *every* beat — this is a metronome trainer;
  obstacles merely add physical stakes on a subset of beats. A missed beat resets
  the streak (never kills the dino by itself; only collisions kill). Whether early
  difficulty levels relax this to obstacle-beats-only is an M3 playtest decision —
  default is every beat.
- Session stats: streak, per-grade counts, error history → histogram + bias readout
  ("you average 18 ms early") on the game-over screen.

### 3.6 `rhythm/calibrate.py`

- Flow: clicks at 100 BPM (accent each bar), player chugs along; collect ≥20 onsets,
  drop first 4, `offset = median(error)` with MAD outlier rejection (|err−med| > 3·MAD).
- Persists `{offset_ms, spread_ms, date, device, detector, blocksize}` to a local
  gitignored `config.json`; game warns when calibration is missing or stale
  (device/detector/blocksize changed).

### 3.7 `game/` (refactor of `main.py`)

- `objects.py`: Dino physics unchanged in feel, but **air time becomes the design
  constant** (~300–350 ms; `JUMP_VEL`/`GRAVITY` derived from it) so jumps fit inside
  beat periods. Obstacle holds its `beat_n` and computes `x(t)` from the conductor.
- `game.py`: states MENU → CALIBRATE → PLAYING → GAME_OVER. Spawner schedules an
  obstacle for beats within a lookahead window; difficulty ramp = obstacle density
  (every 4th beat → every 2nd → every beat) and later BPM steps. Beat pulse visual
  on every click.
- `hud.py`: judgment popup per hit (`PERFECT / −32 ms early`), streak, live error
  bar (tuner-needle style), session histogram on game over.
- `app.py` CLI: `--bpm 80`, `--device`, `--detector energy|flux`, `--chugs-only`,
  `--keyboard-only`, `--debug-hud`.
- Keyboard fallback always active (space = jump) — dev mode without hardware.

### 3.8 V2: songs → levels (`tools/levelgen/` + `levels/`)

- Level JSON: `{version, source{type, title, id}, bpm, beats: [s], downbeats: [s],
  duration_s, generator, generated_at}`.
- Generator CLI (separate uv dependency group `levelgen` — torch stays out of the
  game env): input = local audio file or search string (→ `yt-dlp` search/download,
  mirroring the proven pattern in `agentx/apps/music-scanner-service`); decode via
  `librosa.load` (soundfile decodes MP3 natively — verified); beats + downbeats via
  `beat_this` (checkpoint `final0`, `dbn=False`); BPM sanity-fold into 70–180 by
  median inter-beat interval; write JSON.
- Playback: the song's audio buffer is mixed into the **same duplex output callback**
  positioned by the stream clock (identical mechanism to clicks, one big preloaded
  buffer) — the one-clock invariant holds; obstacles come from `beats[]`
  (downbeats → accents/special obstacles).
- Learning notebook: onset envelope → tempogram → why DL trackers win; run beat_this
  on a real song and inspect.

## 4. Milestones (each = playable increment + notebook chapter)

| # | Deliverable | Notebook chapter | Done when |
|---|---|---|---|
| M0 | Refactor `main.py` → `dino_shred/` package; keyboard game identical; pytest scaffold | — (mechanical; ADR on layout if it deviates) | `uv run python -m dino_shred` plays like today; tests green |
| M1 | AudioEngine capture path + fixtures | `02-hello-audio.ipynb`: devices, capture your guitar, waveform/envelope/spectrogram plots | Recorded chug set in `assets/recordings/` with labels |
| M2 | **First playable**: EnergyGate + clicks + duplex engine; chug → jump (free-run, no judging) | `03-onset-energy.ipynb`: time-domain detection, thresholds, refractory, double-trigger pathology | You play the dino with your guitar |
| M3 | **V1 complete**: Conductor + beat-aligned obstacles + Judge + calibration screen + HUD | `04-clocks-and-latency.ipynb`: measure YOUR rig — callback jitter, ADC/DAC deltas, calibration distribution | Full rhythm-trainer loop with timing feedback |
| M4 | SpectralFlux detector replaces EnergyGate | `05-spectral-flux.ipynb`: windowing, FFT, flux, adaptive thresholds; precision/recall vs aubio referee | Your detector ≥ aubio's F1 on your fixtures |
| M5 | ChugClassifier + `--chugs-only` mode | `06-chug-spectra.ipynb`: palm-mute spectra, band ratios | Open notes ignored in chugs-only mode |
| M6 | **V2**: levelgen CLI + level playback in game | `07-beat-tracking.ipynb`: onset envelope → tempogram → beat_this | Pick a song → play its level |

## 5. Error handling

| Failure | Behavior |
|---|---|
| M-Track absent | Startup error listing devices + hint; `--keyboard-only` works regardless |
| macOS mic permission (stream hangs / all-zero input) | Open with timeout + silence watchdog → actionable message ("grant Microphone to your terminal in System Settings; run from Terminal.app first time") |
| Callback exception (swallowed by PortAudio) | Heartbeat staleness → visible "audio dead" banner, game keeps running on keyboard |
| Buffer over/underruns | Status-flag counter in debug HUD; documented escalation: move detection to worker thread |
| Event queue full | Bounded queue, drop-oldest + counter (never blocks the callback) |
| Calibration missing/stale | Warning banner + prompt to calibrate; judging still works uncalibrated |
| V2: beat_this checkpoint download fails | Cache after first fetch; clear offline error |
| V2: octave-folded BPM | Sanity-fold to 70–180; store confidence; warn on low confidence |

## 6. Testing (pytest)

- **Pure unit** (no audio hardware): Conductor math; Judge windows/streak/one-onset-
  per-beat; calibration median+MAD; ClickScheduler offsets incl. buffer-spanning
  clicks; detectors on synthetic signals (impulse trains, synthetic plucks in noise —
  assert onset times within tolerance).
- **Fixture regression**: real recorded chugs with hand-labeled onsets
  (`assets/recordings/`); detector precision/recall gates.
- **Offline integration**: `OfflineEngine` pumps a WAV through the *same* callback
  code with simulated timestamps → deterministic end-to-end test:
  WAV + BPM in, judgments out.
- **Notebook benchmarks** (dev-only): your detector vs aubio's methods vs
  `librosa.onset` on the fixture set.
- **Manual playtest checklist** per milestone (feel, latency perception, double-
  trigger check, calibration sanity).

## 7. Dependencies

| Group | Packages |
|---|---|
| main | `pygame`, `numpy`, `sounddevice` |
| dev (existing +) | `pytest`, `matplotlib`, `soundfile`, `librosa`, `aubio @ git+…@ad5cf975` (referee only) |
| levelgen (V2, separate) | `beat_this`, `torch` (CPU), `librosa`, `soundfile`, host `yt-dlp` |

## 8. Out of scope (YAGNI)

- Multiple simultaneous input devices / non-macOS platforms (design stays portable
  via the duplex-stream rule, but no testing effort)
- Polyphonic pitch detection / tab recognition
- Online play, score persistence beyond the local config, packaging/distribution
- music-scanner-service ADP integration (V2 uses `yt-dlp` directly; the service can
  be wired in later if the workflow proves useful)

## 9. Open items to validate during implementation

- Real M-Track timestamps/latency (M1 notebook measures; research numbers are from
  built-in devices + published reviews).
- Whether in-callback numpy rFFT causes xruns under game load (fallback: worker thread).
- Jump air-time vs BPM tuning (playtest at M3).
