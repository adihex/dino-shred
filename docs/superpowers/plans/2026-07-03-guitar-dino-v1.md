# Guitar-Dino V1 Rhythm Trainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve dino-shred into a guitar-controlled rhythm trainer: a fixed-BPM metronome clicks through the M-Track Solo, the player's chugs (detected by a from-scratch energy-gate onset detector) make the dino jump, obstacles arrive exactly on beats, and every hit is judged (±30/60/100 ms) with calibration support.

**Architecture:** One full-duplex `sounddevice` stream is the master clock (conductor pattern, ADR 0004): clicks are mixed into the output callback at sample offsets from `outputBufferDacTime`; onsets are timestamped from `inputBufferAdcTime`; judgment is a subtraction. Pygame renders only — obstacle positions are *derived* from beat times each frame, never integrated. Spec: `docs/superpowers/specs/2026-07-03-guitar-dino-design.md`.

**Tech Stack:** Python 3.13, uv, pygame 2.6 (graphics only), numpy, sounddevice 0.5.5, pytest.

## Global Constraints

- Python `>=3.13`; uv-managed; ruff (line 100, double quotes, rules `E,F,I,N,W,UP,B,SIM,C4`); `uv run ty check` must stay clean — full type annotations on all new code.
- `SAMPLE_RATE = 48000`, `BLOCKSIZE = 256` (one hop = 5.333 ms) everywhere.
- **Never initialize `pygame.mixer`** (ADR 0002). All audio through the one duplex stream.
- Real-time callback discipline: no allocation, locks, or I/O inside anything the audio callback calls; buffers preallocated; events cross threads via a bounded queue.
- All times are stream-clock **seconds** (`float`); all signals `np.float32`; errors follow **negative = early**.
- M-Track Solo input: open **2 input channels**; the guitar is the instrument input = **column index 1** (ch1/index 0 is the XLR mic).
- `main.py` (the classic keyboard tutorial game) stays untouched and working.
- Runtime deps limited to `pygame,numpy,sounddevice`; `soundfile`/`pytest` are dev-only; no torch/librosa/aubio in this plan (they arrive in M4+ plans as dev/levelgen groups).
- Interactive milestones (user + guitar required, not subagent tasks): **after Task 7** (hardware check, notebook `02-hello-audio`) and **after Task 14** (calibration + playtest, notebook `04-clocks-and-latency`).

---

### Task 1: Package scaffold, dependencies, derived physics constants

**Files:**
- Modify: `pyproject.toml`
- Create: `dino_shred/__init__.py`, `dino_shred/config.py`
- Test: `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `dino_shred.config` constants used by every later task: `SAMPLE_RATE: int = 48000`, `BLOCKSIZE: int = 256`, `SCREEN_W/SCREEN_H/FPS/GROUND_Y: int`, `DINO_X: int = 80`, `PX_PER_SEC: float = 360.0`, `AIR_TIME_S: float`, `JUMP_HEIGHT_PX: float`, derived `JUMP_VEL: float` (negative) and `GRAVITY: float` (positive, px/frame²), colors `WHITE/BLACK/GREY/DARK: tuple[int, int, int]`.

- [ ] **Step 1: Add dependencies and pytest config**

```bash
uv add numpy sounddevice
uv add --dev pytest soundfile
```

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the failing test**

`tests/__init__.py`: empty file. `tests/test_config.py`:

```python
"""The jump must fit between beats: air time is the design constant (ADR 0004)."""

from dino_shred import config


def test_air_time_is_shorter_than_slowest_beat_period() -> None:
    # V1 default is 80 BPM -> 750 ms period; air time must leave judging room.
    assert config.AIR_TIME_S <= 0.4


def test_discrete_jump_matches_derived_constants() -> None:
    """Simulate the per-frame physics exactly as Dino.update() will run them."""
    y, vy = 0.0, config.JUMP_VEL
    frames = 0
    peak = 0.0
    while True:
        vy += config.GRAVITY
        y += vy
        frames += 1
        peak = min(peak, y)
        if y >= 0.0:
            break
    assert abs(frames - config.AIR_TIME_S * config.FPS) <= 1.5
    assert abs(-peak - config.JUMP_HEIGHT_PX) <= config.JUMP_HEIGHT_PX * 0.15
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dino_shred'`

- [ ] **Step 4: Write the implementation**

`dino_shred/__init__.py`:

```python
"""Dino Shred — a guitar-controlled rhythm trainer built on a Chrome-Dino clone."""
```

`dino_shred/config.py`:

```python
"""Central constants. Gameplay feel and audio geometry live here (ADR 0001, 0004)."""

# --- audio geometry (ADR 0002) ---
SAMPLE_RATE = 48000
BLOCKSIZE = 256  # samples per hop; 5.333 ms at 48 kHz

# --- display ---
SCREEN_W = 800
SCREEN_H = 400
FPS = 60
GROUND_Y = 310

# --- colours ---
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
GREY = (83, 83, 83)
DARK = (50, 50, 50)

# --- gameplay geometry ---
DINO_X = 80  # fixed dino x-position; obstacles arrive here on beats
PX_PER_SEC = 360.0  # obstacle scroll speed (time-derived motion, ADR 0004)

# --- jump physics: AIR TIME is the design constant (ADR 0004) ---
# Jumps must fit inside a beat period. JUMP_VEL/GRAVITY are DERIVED:
#   t_air = 2*v0/g  and  h = v0^2/(2g)   =>   v0 = 4h/t_air,  g = 2*v0/t_air
AIR_TIME_S = 0.35
JUMP_HEIGHT_PX = 90.0
_AIR_FRAMES = AIR_TIME_S * FPS
JUMP_VEL = -4.0 * JUMP_HEIGHT_PX / _AIR_FRAMES  # px/frame, negative = up
GRAVITY = -2.0 * JUMP_VEL / _AIR_FRAMES  # px/frame^2
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: 2 PASS

- [ ] **Step 6: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add pyproject.toml uv.lock dino_shred tests
git commit -m "feat: package scaffold with derived jump physics (air time fits beat period)"
```

---

### Task 2: Port the game objects into the package (keyboard game keeps working)

**Files:**
- Create: `dino_shred/game/__init__.py`, `dino_shred/game/objects.py`
- Create: `tests/conftest.py`
- Test: `tests/test_objects.py`
- Reference (read-only, do NOT edit): `main.py:47-205` — `Dino`, `Obstacle`, `Ground`

**Interfaces:**
- Consumes: `config` constants (Task 1).
- Produces: `Dino` (`jump() -> None`, `duck(is_ducking: bool) -> None`, `update() -> None`, `draw(screen) -> None`, `rect -> pygame.Rect` property, attrs `y: float`, `vy: float`, `on_ground: bool`, `ducking: bool`); `Ground` (`update(speed: float)`, `draw(screen)`); classic `Obstacle` is **not** ported — the beat-anchored version arrives in Task 11.

- [ ] **Step 1: Create headless-pygame conftest**

`tests/conftest.py`:

```python
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402


def pytest_configure() -> None:
    pygame.init()
```

- [ ] **Step 2: Write the failing tests**

`tests/test_objects.py`:

```python
from dino_shred import config
from dino_shred.game.objects import Dino


def test_dino_jump_and_land_cycle() -> None:
    d = Dino()
    assert d.on_ground
    d.jump()
    assert not d.on_ground and d.vy == config.JUMP_VEL
    for _ in range(int(config.AIR_TIME_S * config.FPS) + 3):
        d.update()
    assert d.on_ground and d.vy == 0


def test_no_double_jump_midair() -> None:
    d = Dino()
    d.jump()
    d.update()
    vy_before = d.vy
    d.jump()  # ignored while airborne
    assert d.vy == vy_before


def test_duck_shrinks_hitbox() -> None:
    d = Dino()
    standing = d.rect.height
    d.duck(True)
    assert d.rect.height < standing
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_objects.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dino_shred.game'`

- [ ] **Step 4: Port the classes**

`dino_shred/game/__init__.py`: empty. `dino_shred/game/objects.py`: copy `Dino` and `Ground` **verbatim from `main.py:47-119` and `main.py:175-205`**, then make exactly these edits:

1. Module docstring: `"""Game objects. Ported from main.py; physics constants now derived in config."""`
2. Add imports: `import pygame` and `from dino_shred import config`.
3. Replace every bare constant reference with the config one: `GROUND_Y` → `config.GROUND_Y`, `GRAVITY` → `config.GRAVITY`, `JUMP_VEL` → `config.JUMP_VEL`, `WHITE` → `config.WHITE`, `DARK` → `config.DARK`, `SCREEN_W` → `config.SCREEN_W`, and in `Dino.__init__` set `self.x: float = float(config.DINO_X)` (drop the class-level `X = 80`).
4. Do not port `Obstacle` (replaced in Task 11).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_objects.py -v`
Expected: 3 PASS

- [ ] **Step 6: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/game tests
git commit -m "feat: port Dino and Ground into package with config-derived physics"
```

---

### Task 3: Conductor — the beat grid as pure math

**Files:**
- Create: `dino_shred/rhythm/__init__.py`, `dino_shred/rhythm/conductor.py`
- Test: `tests/test_conductor.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces: `Conductor(t0: float, bpm: float)` with `period -> float` property, `beat_time(n: int) -> float`, `nearest_beat(t: float) -> int`, `beats_in(t_start: float, t_end: float) -> range` (all n with `t_start <= beat_time(n) < t_end`). Later tasks (ClickScheduler, Judge, Spawner, Game) all consume exactly these five names.

- [ ] **Step 1: Write the failing tests**

`tests/test_conductor.py`:

```python
from dino_shred.rhythm.conductor import Conductor


def test_beat_times_at_100_bpm() -> None:
    c = Conductor(t0=100.0, bpm=100.0)
    assert c.period == 0.6
    assert c.beat_time(0) == 100.0
    assert c.beat_time(5) == 103.0


def test_nearest_beat_rounds_correctly() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    assert c.nearest_beat(0.29) == 0
    assert c.nearest_beat(0.31) == 1
    assert c.nearest_beat(2.95) == 5
    assert c.nearest_beat(-0.2) == 0


def test_beats_in_window_half_open() -> None:
    c = Conductor(t0=10.0, bpm=120.0)  # period 0.5
    assert list(c.beats_in(10.0, 11.0)) == [0, 1]  # 11.0 excluded
    assert list(c.beats_in(10.9, 11.6)) == [2, 3]
    assert list(c.beats_in(10.2, 10.4)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_conductor.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

`dino_shred/rhythm/__init__.py`: empty. `dino_shred/rhythm/conductor.py`:

```python
"""The conductor: the beat grid as pure functions of the stream clock (ADR 0004).

Nothing here is ever advanced or accumulated — every quantity is derived fresh
from a timestamp, so there is no error to accumulate and nothing to drift.
"""

import math


class Conductor:
    def __init__(self, t0: float, bpm: float) -> None:
        self.t0 = t0
        self.bpm = bpm

    @property
    def period(self) -> float:
        return 60.0 / self.bpm

    def beat_time(self, n: int) -> float:
        return self.t0 + n * self.period

    def nearest_beat(self, t: float) -> int:
        return round((t - self.t0) / self.period)

    def beats_in(self, t_start: float, t_end: float) -> range:
        """All beat indices n with t_start <= beat_time(n) < t_end."""
        first = math.ceil((t_start - self.t0) / self.period)
        stop = math.ceil((t_end - self.t0) / self.period)
        return range(first, stop)


__all__ = ["Conductor"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_conductor.py -v`
Expected: 3 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/rhythm tests/test_conductor.py
git commit -m "feat: Conductor - beat grid as pure stream-clock math"
```

---
### Task 4: Click synthesis and sample-accurate ClickScheduler

**Files:**
- Create: `dino_shred/audio/__init__.py`, `dino_shred/audio/clicks.py`
- Test: `tests/test_clicks.py`

**Interfaces:**
- Consumes: `Conductor` (Task 3), `config.SAMPLE_RATE`.
- Produces: `make_click(sr: int = 48000, freq: float = 1000.0, dur_ms: float = 5.0, amp: float = 0.5) -> np.ndarray` (float32, 1-D); `ClickScheduler(conductor: Conductor, sr: int = 48000, beats_per_bar: int = 4)` with `render(dac_time: float, out: np.ndarray) -> None` — **adds** clicks into the 1-D float32 buffer `out` covering stream-time `[dac_time, dac_time + len(out)/sr)`. Stateless across calls (spanning clicks recomputed), so it is safe in the callback. Task 6's engine calls exactly `scheduler.render(...)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_clicks.py`:

```python
import numpy as np

from dino_shred.audio.clicks import ClickScheduler, make_click
from dino_shred.rhythm.conductor import Conductor


def test_make_click_shape_and_decay() -> None:
    click = make_click(sr=48000, dur_ms=5.0, amp=0.5)
    assert click.dtype == np.float32
    assert len(click) == 240  # 5 ms at 48 kHz
    assert np.abs(click).max() <= 0.5 + 1e-6
    assert np.abs(click[-10:]).max() < np.abs(click[:10]).max()  # decays


def test_click_lands_at_exact_sample_offset() -> None:
    c = Conductor(t0=1.0, bpm=120.0)  # beats at 1.0, 1.5, 2.0 ...
    s = ClickScheduler(c, sr=48000)
    out = np.zeros(48000, dtype=np.float32)  # covers [0.5, 1.5)
    s.render(dac_time=0.5, out=out)
    onset = int(np.flatnonzero(out != 0.0)[0])
    assert onset == 24000  # (1.0 - 0.5) * 48000


def test_rendering_in_blocks_equals_one_shot() -> None:
    """A click spanning a buffer boundary must be identical to the unblocked render.

    t0=0.001 puts beats at sample 48 + k*19200, so the 240-sample click around
    beat 1 (samples 19248-19487) genuinely crosses the block edge at 19456.
    """
    sr = 48000
    n = 256 * 187  # exactly 187 blocks
    c = Conductor(t0=0.001, bpm=150.0)
    whole = np.zeros(n, dtype=np.float32)
    ClickScheduler(c, sr=sr).render(0.0, whole)

    s2 = ClickScheduler(c, sr=sr)
    blocks = []
    for i in range(0, n, 256):
        b = np.zeros(256, dtype=np.float32)
        s2.render(i / sr, b)
        blocks.append(b)
    np.testing.assert_allclose(np.concatenate(blocks), whole, atol=1e-7)


def test_bar_start_is_accented() -> None:
    c = Conductor(t0=0.0, bpm=60.0)
    s = ClickScheduler(c, sr=48000, beats_per_bar=4)
    beat0 = np.zeros(4800, dtype=np.float32)
    beat1 = np.zeros(4800, dtype=np.float32)
    s.render(0.0, beat0)   # beat 0 -> accent
    s.render(1.0, beat1)   # beat 1 -> normal
    assert np.abs(beat0).max() > np.abs(beat1).max()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_clicks.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

`dino_shred/audio/__init__.py`: empty. `dino_shred/audio/clicks.py`:

```python
"""Metronome click synthesis + sample-accurate scheduling into DAC buffers (ADR 0002).

render() is called from the real-time audio callback: it must not allocate.
All waveforms are preallocated in __init__; scheduling is stateless — a click
whose beat fell before this buffer but whose tail reaches into it is recomputed
from the beat time, so block boundaries are invisible.
"""

import numpy as np

from dino_shred.rhythm.conductor import Conductor


def make_click(
    sr: int = 48000, freq: float = 1000.0, dur_ms: float = 5.0, amp: float = 0.5
) -> np.ndarray:
    n = int(sr * dur_ms / 1000.0)
    t = np.arange(n, dtype=np.float32) / sr
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-t / (dur_ms / 5000.0))
    return (amp * wave / np.abs(wave).max()).astype(np.float32)


class ClickScheduler:
    def __init__(self, conductor: Conductor, sr: int = 48000, beats_per_bar: int = 4) -> None:
        self.conductor = conductor
        self.sr = sr
        self.beats_per_bar = beats_per_bar
        self.click = make_click(sr)
        self.accent = make_click(sr, freq=1500.0, amp=0.8)

    def render(self, dac_time: float, out: np.ndarray) -> None:
        """Add clicks into `out`, which covers [dac_time, dac_time + len(out)/sr)."""
        frames = len(out)
        window_end = dac_time + frames / self.sr
        lookback = dac_time - len(self.accent) / self.sr  # catch tails from earlier beats
        for n in self.conductor.beats_in(lookback, window_end):
            wave = self.accent if n % self.beats_per_bar == 0 else self.click
            offset = round((self.conductor.beat_time(n) - dac_time) * self.sr)
            src_lo = max(0, -offset)
            dst_lo = max(0, offset)
            length = min(len(wave) - src_lo, frames - dst_lo)
            if length > 0:
                out[dst_lo : dst_lo + length] += wave[src_lo : src_lo + length]


__all__ = ["ClickScheduler", "make_click"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_clicks.py -v`
Expected: 4 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/audio tests/test_clicks.py
git commit -m "feat: click synthesis + sample-accurate stateless scheduler"
```

---

### Task 5: OnsetEvent + EnergyGate detector (from scratch, ADR 0003 stage 1)

**Files:**
- Create: `dino_shred/audio/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Consumes: nothing (pure numpy).
- Produces: `OnsetEvent` (frozen dataclass: `t: float`, `strength: float`, `detector: str`); `EnergyGate(sample_rate: int = 48000, hop: int = 256, threshold_db: float = -30.0, hysteresis_db: float = 6.0, refractory_s: float = 0.08)` with `process(frame: np.ndarray, t_frame: float) -> OnsetEvent | None`. **This `process` signature is the detector protocol** — SpectralFlux (M4 plan) and the engine (Task 6) depend on it exactly.

- [ ] **Step 1: Write the failing tests**

`tests/test_detect.py`:

```python
import numpy as np

from dino_shred.audio.detect import EnergyGate, OnsetEvent

SR, HOP = 48000, 256


def synth_plucks(onsets_s: list[float], dur_s: float = 2.0, amp: float = 0.5) -> np.ndarray:
    """Decaying 110 Hz bursts at given onset times — a crude palm-muted chug."""
    sig = np.zeros(int(SR * dur_s), dtype=np.float32)
    t = np.arange(int(SR * 0.30), dtype=np.float32) / SR
    burst = (amp * np.sin(2 * np.pi * 110.0 * t) * np.exp(-t / 0.05)).astype(np.float32)
    for on in onsets_s:
        i = int(on * SR)
        sig[i : i + len(burst)] += burst[: len(sig) - i]
    return sig


def run_detector(gate: EnergyGate, sig: np.ndarray) -> list[OnsetEvent]:
    events = []
    for i in range(0, len(sig) - HOP + 1, HOP):
        ev = gate.process(sig[i : i + HOP], i / SR)
        if ev is not None:
            events.append(ev)
    return events


def test_silence_yields_nothing() -> None:
    gate = EnergyGate()
    assert run_detector(gate, np.zeros(SR, dtype=np.float32)) == []


def test_detects_each_pluck_once_within_two_hops() -> None:
    truth = [0.25, 0.75, 1.25, 1.75]
    events = run_detector(EnergyGate(), synth_plucks(truth))
    assert len(events) == 4
    for ev, expected in zip(events, truth, strict=True):
        assert abs(ev.t - expected) <= 2 * HOP / SR
        assert ev.strength > 0
        assert ev.detector == "energy"


def test_hysteresis_blocks_retrigger_during_decay() -> None:
    # One pluck with a slow decay must produce exactly one event.
    events = run_detector(EnergyGate(), synth_plucks([0.5], dur_s=1.5))
    assert len(events) == 1


def test_refractory_merges_double_hit() -> None:
    # Two hits 40 ms apart (< 80 ms refractory) -> one event.
    events = run_detector(EnergyGate(), synth_plucks([0.5, 0.54]))
    assert len(events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_detect.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

`dino_shred/audio/detect.py`:

```python
"""Onset detectors, built from scratch (ADR 0003).

Stage 1 — EnergyGate: per-hop RMS in dB with a rising-edge threshold,
hysteresis re-arming, and a refractory period. Runs inside the audio
callback: no allocation, O(hop) work, all state is a few floats.

The protocol every detector implements:
    process(frame: np.float32[hop], t_frame: float) -> OnsetEvent | None
`t_frame` is the stream-clock time of frame[0] (inputBufferAdcTime + offset).
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OnsetEvent:
    t: float  # stream-clock seconds of the hit
    strength: float  # dB above threshold
    detector: str


class EnergyGate:
    def __init__(
        self,
        sample_rate: int = 48000,
        hop: int = 256,
        threshold_db: float = -30.0,
        hysteresis_db: float = 6.0,
        refractory_s: float = 0.08,
    ) -> None:
        self.sample_rate = sample_rate
        self.hop = hop
        self.threshold_db = threshold_db
        self.hysteresis_db = hysteresis_db
        self.refractory_s = refractory_s
        self._armed = True
        self._last_onset_t = -1e9

    def process(self, frame: np.ndarray, t_frame: float) -> OnsetEvent | None:
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
        rms_db = 20.0 * float(np.log10(rms + 1e-10))

        if self._armed and rms_db >= self.threshold_db:
            self._armed = False
            if t_frame - self._last_onset_t >= self.refractory_s:
                self._last_onset_t = t_frame
                return OnsetEvent(
                    t=t_frame, strength=rms_db - self.threshold_db, detector="energy"
                )
        elif not self._armed and rms_db < self.threshold_db - self.hysteresis_db:
            self._armed = True  # signal decayed: re-arm for the next attack
        return None


__all__ = ["EnergyGate", "OnsetEvent"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_detect.py -v`
Expected: 4 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/audio/detect.py tests/test_detect.py
git commit -m "feat: EnergyGate onset detector with hysteresis and refractory"
```

---
### Task 6: AudioEngine — duplex stream, callback core, watchdog status

**Files:**
- Create: `dino_shred/audio/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: detector protocol `process(frame, t_frame) -> OnsetEvent | None` (Task 5); `scheduler.render(dac_time, out)` (Task 4); `config.SAMPLE_RATE/BLOCKSIZE`.
- Produces: `DeviceNotFoundError(RuntimeError)`; `find_device(name_substring: str = "M-Track") -> int`; `EngineStatus` (mutable dataclass: `callbacks: int`, `xruns: int`, `queue_drops: int`, `last_callback_time: float`, `peak_hold: float`); `AudioEngine(detector, scheduler, device: int | None = None, input_channel: int = 2, samplerate: int = 48000, blocksize: int = 256)` with `start() -> None`, `stop() -> None`, `time -> float` property, `get_events() -> list[OnsetEvent]`, `take_peak() -> float`, `status: EngineStatus`. Tasks 7 and 14 consume exactly these names. The callback core `_process(indata, outdata, adc_time, dac_time)` is directly testable without hardware.

- [ ] **Step 1: Write the failing tests**

`tests/test_engine.py`:

```python
import numpy as np
import pytest

from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate
from dino_shred.audio.engine import AudioEngine, DeviceNotFoundError, find_device
from dino_shred.rhythm.conductor import Conductor

SR, BS = 48000, 256


def make_engine() -> AudioEngine:
    cond = Conductor(t0=10.0, bpm=120.0)
    return AudioEngine(
        detector=EnergyGate(), scheduler=ClickScheduler(cond, sr=SR), input_channel=2
    )


def blocks(sig: np.ndarray) -> list[np.ndarray]:
    """Split mono signal into (BS, 2) stereo blocks with guitar on column 1."""
    out = []
    for i in range(0, len(sig) - BS + 1, BS):
        b = np.zeros((BS, 2), dtype=np.float32)
        b[:, 1] = sig[i : i + BS]
        out.append(b)
    return out


def test_onset_events_carry_adc_timestamps() -> None:
    eng = make_engine()
    sig = np.zeros(SR, dtype=np.float32)
    sig[24000 : 24000 + 2400] = 0.5  # step onset at +0.5 s
    outdata = np.zeros((BS, 2), dtype=np.float32)
    for i, block in enumerate(blocks(sig)):
        adc = 50.0 + i * BS / SR  # stream clock starts at 50.0
        eng._process(block, outdata, adc_time=adc, dac_time=adc + 0.01)
    events = eng.get_events()
    assert len(events) == 1
    assert abs(events[0].t - 50.5) <= 2 * BS / SR


def test_clicks_rendered_into_both_output_channels() -> None:
    eng = make_engine()
    indata = np.zeros((BS, 2), dtype=np.float32)
    outdata = np.ones((BS, 2), dtype=np.float32)  # uninitialized memory simulation
    # dac window [10.0, 10.0053) contains beat 0 of the conductor (t0=10.0)
    eng._process(indata, outdata, adc_time=9.99, dac_time=10.0)
    assert np.abs(outdata[:, 0]).max() > 0
    np.testing.assert_array_equal(outdata[:, 0], outdata[:, 1])
    assert outdata[0, 0] != 1.0  # buffer was cleared, not accumulated onto


def test_queue_overflow_drops_and_counts() -> None:
    eng = make_engine()
    eng.events.maxsize = 2
    sig_on = np.full(BS, 0.5, dtype=np.float32)
    sig_off = np.zeros(BS, dtype=np.float32)
    outdata = np.zeros((BS, 2), dtype=np.float32)
    t = 0.0
    for _ in range(5):  # 5 distinct onsets, queue holds 2
        # 1 hot block + 19 silent blocks = bursts ~107 ms apart (> 80 ms refractory),
        # with full re-arm (silence) between them -> exactly one event per burst.
        for sig in (sig_on,) + (sig_off,) * 19:
            block = np.zeros((BS, 2), dtype=np.float32)
            block[:, 1] = sig
            eng._process(block, outdata, adc_time=t, dac_time=t + 0.01)
            t += BS / SR
    assert eng.status.queue_drops == 3
    assert len(eng.get_events()) == 2


def test_peak_hold_take_and_reset() -> None:
    eng = make_engine()
    outdata = np.zeros((BS, 2), dtype=np.float32)
    block = np.zeros((BS, 2), dtype=np.float32)
    block[:, 1] = 0.25
    eng._process(block, outdata, adc_time=0.0, dac_time=0.01)
    assert eng.take_peak() == pytest.approx(0.25)
    assert eng.take_peak() == 0.0  # reset after read (silence watchdog polls this)


def test_find_device_raises_with_device_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    import dino_shred.audio.engine as engine_mod

    monkeypatch.setattr(
        engine_mod.sd,
        "query_devices",
        lambda: [{"name": "MacBook Pro Microphone", "max_input_channels": 1}],
    )
    with pytest.raises(DeviceNotFoundError, match="MacBook Pro Microphone"):
        find_device("M-Track")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

`dino_shred/audio/engine.py`:

```python
"""The audio engine: ONE full-duplex stream, the master clock of the game (ADR 0002).

The PortAudio callback runs on a real-time thread. Rules inside _process:
no locks, no I/O, no prints, no unbounded work. Small numpy temporaries are
accepted pragmatically (Python-level, bounded by blocksize); events cross to
the game thread through a bounded non-blocking queue.

PortAudio swallows callback exceptions, so liveness is exposed via
EngineStatus.last_callback_time (the game shows an "audio dead" banner if
it goes stale) and silent input is detected by polling take_peak().
"""

import queue
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import sounddevice as sd

from dino_shred.audio.clicks import ClickScheduler
from dino_shred.audio.detect import EnergyGate, OnsetEvent


class DeviceNotFoundError(RuntimeError):
    pass


def find_device(name_substring: str = "M-Track") -> int:
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name_substring.lower() in dev["name"].lower() and dev["max_input_channels"] >= 2:
            return i
    listing = "\n".join(f"  [{i}] {d['name']}" for i, d in enumerate(devices))
    raise DeviceNotFoundError(
        f"No input device matching {name_substring!r}. Available devices:\n{listing}\n"
        "Plug in the interface, or pass --device <index> / --keyboard-only."
    )


@dataclass
class EngineStatus:
    callbacks: int = 0
    xruns: int = 0
    queue_drops: int = 0
    last_callback_time: float = 0.0
    peak_hold: float = field(default=0.0)


class AudioEngine:
    def __init__(
        self,
        detector: EnergyGate,
        scheduler: ClickScheduler | None,
        device: int | None = None,
        input_channel: int = 2,
        samplerate: int = 48000,
        blocksize: int = 256,
    ) -> None:
        self.detector = detector
        self.scheduler = scheduler
        self.device = device
        self.input_channel = input_channel  # 1-based; M-Track instrument input is 2
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.events: queue.Queue[OnsetEvent] = queue.Queue(maxsize=64)
        self.status = EngineStatus()
        self._mono_out = np.zeros(blocksize, dtype=np.float32)
        self._stream: sd.Stream | None = None

    # -- callback core (hardware-free testable) --------------------------------

    def _process(
        self, indata: np.ndarray, outdata: np.ndarray, adc_time: float, dac_time: float
    ) -> None:
        outdata[:] = 0.0  # duplex outdata is uninitialized memory: always clear
        if self.scheduler is not None:
            self._mono_out[:] = 0.0
            self.scheduler.render(dac_time, self._mono_out)
            outdata[:, 0] = self._mono_out
            outdata[:, 1] = self._mono_out

        frame = indata[:, self.input_channel - 1]
        peak = float(np.abs(frame).max()) if len(frame) else 0.0
        self.status.peak_hold = max(self.status.peak_hold, peak)

        event = self.detector.process(frame, adc_time)
        if event is not None:
            try:
                self.events.put_nowait(event)
            except queue.Full:
                self.status.queue_drops += 1

        self.status.callbacks += 1
        self.status.last_callback_time = dac_time

    def _callback(
        self, indata: np.ndarray, outdata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        if status:
            self.status.xruns += 1
        self._process(indata, outdata, time_info.inputBufferAdcTime, time_info.outputBufferDacTime)

    # -- lifecycle --------------------------------------------------------------

    def start(self) -> None:
        device = self.device if self.device is not None else find_device()
        extra = sd.CoreAudioSettings(change_device_parameters=True) if sys.platform == "darwin" else None
        self._stream = sd.Stream(
            device=(device, device),
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="float32",
            channels=(2, 2),
            latency="low",
            extra_settings=extra,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @property
    def time(self) -> float:
        if self._stream is None:
            raise RuntimeError("engine not started")
        return self._stream.time

    # -- game-thread helpers ------------------------------------------------------

    def get_events(self) -> list[OnsetEvent]:
        out: list[OnsetEvent] = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def take_peak(self) -> float:
        """Return and reset the peak input level (silence-watchdog poll)."""
        peak = self.status.peak_hold
        self.status.peak_hold = 0.0
        return peak


__all__ = ["AudioEngine", "DeviceNotFoundError", "EngineStatus", "find_device"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -v`
Expected: 5 PASS

- [ ] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/audio/engine.py tests/test_engine.py
git commit -m "feat: AudioEngine duplex callback core with watchdog status"
```

---

### Task 7: Hardware check tool (first guitar moment — interactive milestone after this)

**Files:**
- Create: `dino_shred/audio/check.py`
- Test: `tests/test_check.py` (pure helper only; the tool itself is manual-verified)

**Interfaces:**
- Consumes: `AudioEngine`, `find_device`, `DeviceNotFoundError` (Task 6), `EnergyGate` (Task 5), `ClickScheduler` (Task 4), `Conductor` (Task 3).
- Produces: `format_hit(onset_t: float, conductor: Conductor) -> str` (e.g. `"beat   12  -23.4 ms early"`); CLI `uv run python -m dino_shred.audio.check [--bpm 100] [--device N] [--input-channel 2] [--list] [--seconds 30]`.

- [x] **Step 1: Write the failing test for the pure helper**

`tests/test_check.py`:

```python
from dino_shred.audio.check import format_hit
from dino_shred.rhythm.conductor import Conductor


def test_format_hit_reports_signed_error() -> None:
    c = Conductor(t0=100.0, bpm=100.0)
    assert "early" in format_hit(102.98, c) and "-20.0 ms" in format_hit(102.98, c)
    assert "late" in format_hit(103.03, c) and "+30.0 ms" in format_hit(103.03, c)
    assert "beat 5" in format_hit(102.98, c).replace("  ", " ")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_check.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/audio/check.py`:

```python
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
    return f"beat {n:4d}  {err_ms:+7.1f} ms {side}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bpm", type=float, default=100.0)
    parser.add_argument("--device", type=int, default=None)
    parser.add_argument("--input-channel", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--list", action="store_true", help="list devices and exit")
    args = parser.parse_args()

    if args.list:
        print(sd.query_devices())
        return

    try:
        device = args.device if args.device is not None else find_device()
    except DeviceNotFoundError as e:
        raise SystemExit(str(e)) from e

    # Bootstrap: engine needs a scheduler, scheduler needs t0 from the engine's
    # clock. Start with scheduler=None, then attach once the stream is running.
    engine = AudioEngine(
        detector=EnergyGate(), scheduler=None, device=device,
        input_channel=args.input_channel,
    )
    engine.start()
    conductor = Conductor(t0=engine.time + 1.0, bpm=args.bpm)
    engine.scheduler = ClickScheduler(conductor)

    print(f"Clicking at {args.bpm:g} BPM for {args.seconds:g}s — chug along! Ctrl-C stops.")
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
        print(f"\n{len(errors)} hits, median error {med:+.1f} ms "
              f"(xruns={engine.status.xruns}, drops={engine.status.queue_drops})")
    else:
        print("\nNo hits detected.")


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Run test + lint, commit**

Run: `uv run pytest tests/test_check.py -v` — Expected: 1 PASS

```bash
uv run ruff check && uv run ty check
git add dino_shred/audio/check.py tests/test_check.py
git commit -m "feat: hardware check tool - click + live chug timing readout"
```

- [ ] **Step 5: INTERACTIVE MILESTONE (user + guitar) — not a subagent step**

With the M-Track plugged in, from Terminal.app: `uv run python -m dino_shred.audio.check --bpm 100`.
Checklist: ☐ TCC prompt appeared and was granted ☐ clicks audible in M-Track headphones ☐ chugs print with plausible errors ☐ no xruns. Then co-author notebook `notebooks/02-hello-audio.ipynb` with the user (waveform/envelope/spectrogram of their guitar; record fixtures into `assets/recordings/`). Tune `EnergyGate.threshold_db` to their signal level here if needed.

---
### Task 8: Judge — timing windows, one-onset-per-beat, miss sweeping

**Files:**
- Create: `dino_shred/rhythm/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `Conductor` (Task 3).
- Produces: `Grade` (Enum: `PERFECT, GOOD, OK, MISS, OFF_GRID`); `Judgment` (frozen dataclass: `grade: Grade`, `beat_n: int`, `error_s: float | None` — None for MISS); `Judge(conductor: Conductor, offset_s: float = 0.0, first_beat: int = 0, max_window_s: float = 0.100, sweep_margin_s: float = 0.05)` with `judge_onset(onset_t: float) -> Judgment`, `sweep_misses(now: float) -> list[Judgment]`, attrs `streak: int`, `best_streak: int`, `counts: dict[Grade, int]`, `errors: list[float]`. Task 13's game loop consumes exactly these. Sign convention: **negative error = early**.

- [x] **Step 1: Write the failing tests**

`tests/test_judge.py`:

```python
import pytest

from dino_shred.rhythm.conductor import Conductor
from dino_shred.rhythm.judge import Grade, Judge


def make_judge(**kw) -> Judge:
    return Judge(Conductor(t0=100.0, bpm=100.0), **kw)  # beats at 100.0, 100.6, ...


@pytest.mark.parametrize(
    ("err", "grade"),
    [(0.0, Grade.PERFECT), (-0.030, Grade.PERFECT), (0.031, Grade.GOOD),
     (-0.060, Grade.GOOD), (0.061, Grade.OK), (-0.100, Grade.OK)],
)
def test_window_boundaries(err: float, grade: Grade) -> None:
    j = make_judge()
    assert j.judge_onset(100.6 + err).grade is grade


def test_far_offbeat_is_off_grid_and_keeps_streak() -> None:
    j = make_judge()
    j.judge_onset(100.6)
    assert j.streak == 1
    verdict = j.judge_onset(100.6 + 0.25)  # way off any beat
    assert verdict.grade is Grade.OFF_GRID
    assert j.streak == 1  # off-grid never touches score


def test_one_onset_per_beat() -> None:
    j = make_judge()
    assert j.judge_onset(100.59).grade is Grade.PERFECT
    assert j.judge_onset(100.62).grade is Grade.OFF_GRID  # beat 1 already consumed


def test_calibration_offset_is_subtracted() -> None:
    j = make_judge(offset_s=0.050)  # detector+player measured 50 ms late
    assert j.judge_onset(100.6 + 0.050).grade is Grade.PERFECT


def test_sweep_marks_misses_and_resets_streak() -> None:
    j = make_judge()
    j.judge_onset(100.6)  # hit beat 1
    # advance past beats 2 and 3 without onsets (+ margin 0.05 + window 0.1)
    misses = j.sweep_misses(now=101.8 + 0.16)
    assert [m.beat_n for m in misses] == [0, 2, 3]  # beat 0 also never hit
    assert all(m.grade is Grade.MISS for m in misses)
    assert j.streak == 0
    assert j.counts[Grade.MISS] == 3


def test_sweep_respects_margin_for_inflight_events() -> None:
    j = make_judge()
    # beat 1 window closes at 100.70; sweep margin keeps it claimable until 100.75,
    # so a sweep at 100.72 only expires beat 0 and a late event can still claim beat 1.
    assert [m.beat_n for m in j.sweep_misses(now=100.72)] == [0]
    assert j.judge_onset(100.68).grade is Grade.OK


def test_first_beat_skips_count_in() -> None:
    j = make_judge(first_beat=4)
    assert [m.beat_n for m in j.sweep_misses(now=103.0)] == [4]  # beats 0-3 ignored
    assert j.judge_onset(100.6).grade is Grade.OFF_GRID  # count-in beat not judged
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_judge.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/rhythm/judge.py`:

```python
"""Judgment: error = onset_t - offset - beat_time(nearest)  (ADR 0004).

Windows are half-widths; negative error = early. Game rule (spec 3.5): the
player chugs every beat; a missed beat resets the streak; off-grid extras
never affect score. sweep_misses() trails `now` by a safety margin so an
onset still sitting in the event queue can claim its beat.
"""

from dataclasses import dataclass
from enum import Enum

from dino_shred.rhythm.conductor import Conductor


class Grade(Enum):
    PERFECT = "perfect"
    GOOD = "good"
    OK = "ok"
    MISS = "miss"
    OFF_GRID = "off_grid"


WINDOWS: dict[Grade, float] = {Grade.PERFECT: 0.030, Grade.GOOD: 0.060, Grade.OK: 0.100}


@dataclass(frozen=True)
class Judgment:
    grade: Grade
    beat_n: int
    error_s: float | None  # None for MISS


class Judge:
    def __init__(
        self,
        conductor: Conductor,
        offset_s: float = 0.0,
        first_beat: int = 0,
        max_window_s: float = 0.100,
        sweep_margin_s: float = 0.05,
    ) -> None:
        self.conductor = conductor
        self.offset_s = offset_s
        self.first_beat = first_beat
        self.max_window_s = max_window_s
        self.sweep_margin_s = sweep_margin_s
        self.streak = 0
        self.best_streak = 0
        self.counts: dict[Grade, int] = {g: 0 for g in Grade}
        self.errors: list[float] = []
        self._consumed: set[int] = set()
        self._next_sweep = first_beat

    def judge_onset(self, onset_t: float) -> Judgment:
        t = onset_t - self.offset_s
        n = self.conductor.nearest_beat(t)
        error = t - self.conductor.beat_time(n)
        claimable = (
            n >= self.first_beat
            and n >= self._next_sweep  # beat not already swept as missed
            and n not in self._consumed
            and abs(error) <= self.max_window_s
        )
        if not claimable:
            self.counts[Grade.OFF_GRID] += 1
            return Judgment(Grade.OFF_GRID, n, error)

        self._consumed.add(n)
        if abs(error) <= WINDOWS[Grade.PERFECT]:
            grade = Grade.PERFECT
        elif abs(error) <= WINDOWS[Grade.GOOD]:
            grade = Grade.GOOD
        else:
            grade = Grade.OK
        self.counts[grade] += 1
        self.errors.append(error)
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        return Judgment(grade, n, error)

    def sweep_misses(self, now: float) -> list[Judgment]:
        """Mark beats whose claim window has fully passed and that got no onset."""
        t = now - self.offset_s - self.sweep_margin_s
        misses: list[Judgment] = []
        while self.conductor.beat_time(self._next_sweep) + self.max_window_s < t:
            n = self._next_sweep
            self._next_sweep += 1
            if n in self._consumed:
                self._consumed.discard(n)  # keep the set bounded
            else:
                self.counts[Grade.MISS] += 1
                self.streak = 0
                misses.append(Judgment(Grade.MISS, n, None))
        return misses


__all__ = ["WINDOWS", "Grade", "Judge", "Judgment"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_judge.py -v`
Expected: all PASS (11 including parametrized)

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/rhythm/judge.py tests/test_judge.py
git commit -m "feat: Judge - timing windows, per-beat claiming, miss sweeping"
```

---

### Task 9: Calibration — median offset with MAD outlier rejection

**Files:**
- Create: `dino_shred/rhythm/calibrate.py`
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Consumes: `Conductor` (Task 3).
- Produces: `compute_offset(errors: list[float]) -> tuple[float, float]` (median, MAD after 3·MAD rejection); `CalibrationSession(conductor: Conductor, min_hits: int = 20, discard: int = 4)` with `add_onset(onset_t: float) -> None`, `hits: int` property (post-discard count, clamped ≥0), `is_complete: bool` property, `result() -> tuple[float, float]`. Task 13's CALIBRATE state consumes exactly these.

- [x] **Step 1: Write the failing tests**

`tests/test_calibrate.py`:

```python
import pytest

from dino_shred.rhythm.calibrate import CalibrationSession, compute_offset
from dino_shred.rhythm.conductor import Conductor


def test_compute_offset_median_and_spread() -> None:
    offset, spread = compute_offset([0.040, 0.045, 0.050, 0.055, 0.060])
    assert offset == pytest.approx(0.050)
    assert spread == pytest.approx(0.005)


def test_outliers_rejected_by_mad() -> None:
    errors = [0.048, 0.050, 0.052, 0.049, 0.051, 0.450]  # one wild miss-hit
    offset, _ = compute_offset(errors)
    assert offset == pytest.approx(0.050, abs=0.002)


def test_identical_errors_no_zero_division() -> None:
    offset, spread = compute_offset([0.05, 0.05, 0.05])
    assert (offset, spread) == (0.05, 0.0)


def test_session_discards_warmup_and_completes() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    s = CalibrationSession(c, min_hits=20, discard=4)
    for n in range(24):
        s.add_onset(c.beat_time(n) + 0.030)  # consistently 30 ms late
        assert s.is_complete is (n >= 23)
    offset, spread = s.result()
    assert offset == pytest.approx(0.030)
    assert spread == pytest.approx(0.0, abs=1e-9)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_calibrate.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/rhythm/calibrate.py`:

```python
"""Latency calibration (spec 3.6): chug along with the click; the median error
is the constant part of detector delay + player bias. MAD rejection discards
wild outliers (missed/extra hits) before taking the median.
"""

import statistics

from dino_shred.rhythm.conductor import Conductor


def compute_offset(errors: list[float]) -> tuple[float, float]:
    med = statistics.median(errors)
    mad = statistics.median(abs(e - med) for e in errors)
    if mad > 0.0:
        kept = [e for e in errors if abs(e - med) <= 3.0 * mad]
    else:
        kept = list(errors)
    return statistics.median(kept), mad


class CalibrationSession:
    def __init__(self, conductor: Conductor, min_hits: int = 20, discard: int = 4) -> None:
        self.conductor = conductor
        self.min_hits = min_hits
        self.discard = discard
        self._errors: list[float] = []

    def add_onset(self, onset_t: float) -> None:
        n = self.conductor.nearest_beat(onset_t)
        self._errors.append(onset_t - self.conductor.beat_time(n))

    @property
    def hits(self) -> int:
        return max(0, len(self._errors) - self.discard)

    @property
    def is_complete(self) -> bool:
        return self.hits >= self.min_hits

    def result(self) -> tuple[float, float]:
        return compute_offset(self._errors[self.discard :])


__all__ = ["CalibrationSession", "compute_offset"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_calibrate.py -v`
Expected: 4 PASS

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/rhythm/calibrate.py tests/test_calibrate.py
git commit -m "feat: calibration - median offset with MAD outlier rejection"
```

---

### Task 10: Calibration persistence + staleness check

**Files:**
- Modify: `dino_shred/config.py` (append), `.gitignore` (append `config.json`)
- Test: `tests/test_config_persistence.py`

**Interfaces:**
- Consumes: constants from Task 1 (same module).
- Produces: `CalibrationData` (frozen dataclass: `offset_s: float`, `spread_s: float`, `date: str`, `device: str`, `detector: str`, `blocksize: int`); `save_calibration(data: CalibrationData, path: Path = CONFIG_PATH) -> None`; `load_calibration(path: Path = CONFIG_PATH) -> CalibrationData | None`; `CONFIG_PATH: Path` (= `Path("config.json")`); method `CalibrationData.is_stale(device: str, detector: str, blocksize: int) -> bool`. Task 13/14 consume exactly these.

- [x] **Step 1: Write the failing tests**

`tests/test_config_persistence.py`:

```python
from pathlib import Path

from dino_shred.config import CalibrationData, load_calibration, save_calibration


def make_data() -> CalibrationData:
    return CalibrationData(
        offset_s=0.032, spread_s=0.008, date="2026-07-03",
        device="M-Track Solo", detector="energy", blocksize=256,
    )


def test_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    save_calibration(make_data(), p)
    assert load_calibration(p) == make_data()


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_calibration(tmp_path / "absent.json") is None


def test_corrupt_file_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text("{not json")
    assert load_calibration(p) is None


def test_staleness_on_any_mismatch() -> None:
    d = make_data()
    assert not d.is_stale("M-Track Solo", "energy", 256)
    assert d.is_stale("M-Track Solo", "flux", 256)      # detector changed
    assert d.is_stale("M-Track Solo", "energy", 128)    # blocksize changed
    assert d.is_stale("Scarlett 2i2", "energy", 256)    # interface changed
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config_persistence.py -v`
Expected: FAIL — ImportError (names don't exist yet)

- [x] **Step 3: Implement — append to `dino_shred/config.py`**

```python
# --- calibration persistence (spec 3.6) -------------------------------------
import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_PATH = Path("config.json")


@dataclass(frozen=True)
class CalibrationData:
    offset_s: float
    spread_s: float
    date: str
    device: str
    detector: str
    blocksize: int

    def is_stale(self, device: str, detector: str, blocksize: int) -> bool:
        """Calibration only holds for the exact setup it was measured under."""
        return (self.device, self.detector, self.blocksize) != (device, detector, blocksize)


def save_calibration(data: CalibrationData, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(asdict(data), indent=2))


def load_calibration(path: Path = CONFIG_PATH) -> CalibrationData | None:
    try:
        return CalibrationData(**json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        return None
```

Move the `import json` / `from dataclasses ...` / `from pathlib ...` lines to the top of the module with the existing imports (ruff will demand it).

Append to `.gitignore`:

```
# per-machine calibration
config.json
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config_persistence.py -v`
Expected: 4 PASS

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/config.py tests/test_config_persistence.py .gitignore
git commit -m "feat: calibration persistence with setup-staleness check"
```

---
### Task 11: Beat-anchored Obstacle + Spawner (time-derived motion, ADR 0004)

**Files:**
- Modify: `dino_shred/game/objects.py` (append `Obstacle`)
- Create: `dino_shred/game/spawner.py`
- Test: `tests/test_spawner.py`

**Interfaces:**
- Consumes: `Conductor` (Task 3), `config` (Task 1), `Dino` (Task 2 — for width alignment).
- Produces: `Obstacle(beat_n: int, conductor: Conductor, variant: int)` with `x(t: float) -> float`, `rect(t: float) -> pygame.Rect`, `is_gone(t: float) -> bool`, `draw(screen: pygame.Surface, t: float) -> None`, attrs `beat_n, variant, width, height, y`; `Spawner(conductor: Conductor, first_beat: int, horizon_s: float = 3.0, seed: int | None = None)` with `update(t: float) -> list[Obstacle]` (newly spawned this call) and `density(beat_n: int) -> int`. V1 spawns **cactus variants (0, 1) only** — birds require ducking, which a guitar can't express until the chug classifier exists (M5).

- [x] **Step 1: Write the failing tests**

`tests/test_spawner.py`:

```python
from dino_shred import config
from dino_shred.game.objects import Dino, Obstacle
from dino_shred.game.spawner import Spawner
from dino_shred.rhythm.conductor import Conductor


def test_obstacle_centered_on_dino_exactly_at_its_beat() -> None:
    c = Conductor(t0=50.0, bpm=100.0)
    obs = Obstacle(beat_n=8, conductor=c, variant=0)
    beat_t = c.beat_time(8)
    assert obs.rect(beat_t).centerx == Dino().rect.centerx


def test_obstacle_moves_left_at_px_per_sec() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    obs = Obstacle(beat_n=4, conductor=c, variant=1)
    assert obs.x(1.0) - obs.x(1.5) == 0.5 * config.PX_PER_SEC


def test_obstacle_is_gone_after_leaving_screen() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    obs = Obstacle(beat_n=0, conductor=c, variant=0)
    assert not obs.is_gone(c.beat_time(0))
    assert obs.is_gone(c.beat_time(0) + 2.0)  # long gone left of the screen


def test_spawner_every_4th_beat_early_no_duplicates() -> None:
    c = Conductor(t0=10.0, bpm=120.0)  # period 0.5: beat n at 10.0 + n*0.5
    s = Spawner(c, first_beat=4, horizon_s=3.0, seed=7)
    first = s.update(t=10.0)  # horizon < 13.0 covers beats 4,5 -> eligible: 4
    assert [o.beat_n for o in first] == [4]
    assert s.update(t=10.0) == []  # idempotent: nothing new until time advances
    later = s.update(t=11.1)  # horizon < 14.1 adds beats 6,7,8 -> eligible: 8
    assert [o.beat_n for o in later] == [8]
    assert all(o.variant in (0, 1) for o in first + later)


def test_density_ramps_4_2_1() -> None:
    c = Conductor(t0=0.0, bpm=100.0)
    s = Spawner(c, first_beat=4)
    assert s.density(4) == 4       # first 16 beats: every 4th
    assert s.density(4 + 16) == 2  # next stretch: every 2nd
    assert s.density(4 + 48) == 1  # then every beat
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spawner.py -v`
Expected: FAIL — ImportError

- [x] **Step 3: Implement**

Append to `dino_shred/game/objects.py`:

```python
class Obstacle:
    """A cactus bound to a beat: its position is DERIVED from time (ADR 0004).

    x(t) is computed fresh every frame from the conductor — never integrated —
    so the obstacle's center crosses the dino's center exactly at beat_time(n).
    Variants: 0 = small cactus, 1 = tall cactus. (Birds return with the chug
    classifier in M5 — a guitar can't duck yet.)
    """

    SIZES = {0: (20, 40), 1: (24, 54)}

    def __init__(self, beat_n: int, conductor: "Conductor", variant: int) -> None:
        self.beat_n = beat_n
        self.conductor = conductor
        self.variant = variant
        self.width, self.height = self.SIZES[variant]
        self.y = config.GROUND_Y - self.height
        # align obstacle center with dino center at the beat
        dino_center = config.DINO_X + Dino.WIDTH / 2
        self._x_at_beat = dino_center - self.width / 2

    def x(self, t: float) -> float:
        dt = self.conductor.beat_time(self.beat_n) - t
        return self._x_at_beat + dt * config.PX_PER_SEC

    def rect(self, t: float) -> pygame.Rect:
        x = self.x(t)
        return pygame.Rect(int(x) + 2, self.y + 2, self.width - 4, self.height - 4)

    def is_gone(self, t: float) -> bool:
        return self.x(t) + self.width < -50

    def draw(self, screen: pygame.Surface, t: float) -> None:
        pygame.draw.rect(
            screen, config.GREY, pygame.Rect(int(self.x(t)), self.y, self.width, self.height)
        )
```

Add at the top of `objects.py`: `from dino_shred.rhythm.conductor import Conductor` (and drop the quotes on the annotation if ty prefers the direct import).

Create `dino_shred/game/spawner.py`:

```python
"""Obstacle spawner: schedules obstacles onto future beats (spec 3.7).

Difficulty ramps by density — every 4th beat, then every 2nd, then every beat.
Spawning looks `horizon_s` ahead so obstacles enter from off-screen right.
"""

import random

from dino_shred.game.objects import Obstacle
from dino_shred.rhythm.conductor import Conductor


class Spawner:
    def __init__(
        self,
        conductor: Conductor,
        first_beat: int,
        horizon_s: float = 3.0,
        seed: int | None = None,
    ) -> None:
        self.conductor = conductor
        self.first_beat = first_beat
        self.horizon_s = horizon_s
        self._rng = random.Random(seed)
        self._next_beat = first_beat

    def density(self, beat_n: int) -> int:
        played = beat_n - self.first_beat
        if played < 16:
            return 4
        if played < 48:
            return 2
        return 1

    def update(self, t: float) -> list[Obstacle]:
        spawned: list[Obstacle] = []
        while self.conductor.beat_time(self._next_beat) < t + self.horizon_s:
            n = self._next_beat
            self._next_beat += 1
            if (n - self.first_beat) % self.density(n) == 0:
                spawned.append(Obstacle(n, self.conductor, self._rng.randint(0, 1)))
        return spawned


__all__ = ["Spawner"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spawner.py -v`
Expected: 5 PASS

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/game tests/test_spawner.py
git commit -m "feat: beat-anchored obstacles with time-derived motion + density-ramp spawner"
```

---

### Task 12: HUD — judgment feedback, error bar, histogram (pure helpers tested)

**Files:**
- Create: `dino_shred/game/hud.py`
- Test: `tests/test_hud.py`

**Interfaces:**
- Consumes: `Grade`, `Judgment` (Task 8), `config` (Task 1).
- Produces: `format_error(error_s: float | None) -> str`; `error_bar_x(error_s: float, width: int, max_s: float = 0.1) -> int`; `histogram_bins(errors: list[float], n_bins: int = 20, range_s: float = 0.1) -> list[int]`; `GRADE_COLORS: dict[Grade, tuple[int, int, int]]`; `Hud()` with `add(judgment: Judgment, t: float) -> None`, `draw(screen: pygame.Surface, t: float, streak: int, bpm: float) -> None`, `draw_summary(screen: pygame.Surface, errors: list[float], counts: dict[Grade, int], best_streak: int) -> None`. Task 13 consumes `Hud`, Task 14 only renders through Task 13.

- [x] **Step 1: Write the failing tests**

`tests/test_hud.py`:

```python
from dino_shred.game.hud import error_bar_x, format_error, histogram_bins


def test_format_error_signs_and_miss() -> None:
    assert format_error(-0.032) == "-32 ms early"
    assert format_error(0.045) == "+45 ms late"
    assert format_error(0.0) == "+0 ms late"
    assert format_error(None) == "MISS"


def test_error_bar_maps_range_to_pixels() -> None:
    assert error_bar_x(0.0, width=200) == 100          # centered
    assert error_bar_x(-0.1, width=200) == 0           # full early
    assert error_bar_x(0.1, width=200) == 200          # full late
    assert error_bar_x(0.5, width=200) == 200          # clamped


def test_histogram_bins_count_and_clip() -> None:
    bins = histogram_bins([-0.09, -0.01, 0.0, 0.01, 0.09, 0.3], n_bins=4, range_s=0.1)
    assert len(bins) == 4
    assert sum(bins) == 6  # out-of-range clipped into edge bins
    assert bins[1] + bins[2] == 3  # the three near-zero errors sit centrally
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_hud.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/game/hud.py`:

```python
"""HUD: per-hit judgment popups, streak, live error bar, session histogram.

Pure helpers (formatting, bar mapping, binning) are unit-tested; the draw
methods are thin pygame rendering over them. Sign convention: negative = early.
"""

import pygame

from dino_shred import config
from dino_shred.rhythm.judge import Grade, Judgment

GRADE_COLORS: dict[Grade, tuple[int, int, int]] = {
    Grade.PERFECT: (46, 160, 67),
    Grade.GOOD: (9, 105, 218),
    Grade.OK: (154, 103, 0),
    Grade.MISS: (207, 34, 46),
    Grade.OFF_GRID: (110, 119, 129),
}

POPUP_LIFETIME_S = 0.8


def format_error(error_s: float | None) -> str:
    if error_s is None:
        return "MISS"
    ms = round(error_s * 1000)
    return f"{ms:+d} ms {'early' if ms < 0 else 'late'}"


def error_bar_x(error_s: float, width: int, max_s: float = 0.1) -> int:
    clamped = max(-max_s, min(max_s, error_s))
    return round((clamped + max_s) / (2 * max_s) * width)


def histogram_bins(errors: list[float], n_bins: int = 20, range_s: float = 0.1) -> list[int]:
    bins = [0] * n_bins
    for e in errors:
        frac = (max(-range_s, min(range_s, e)) + range_s) / (2 * range_s)
        bins[min(n_bins - 1, int(frac * n_bins))] += 1
    return bins


class Hud:
    def __init__(self) -> None:
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 40)
        self._popup: tuple[Judgment, float] | None = None  # (judgment, born_t)

    def add(self, judgment: Judgment, t: float) -> None:
        self._popup = (judgment, t)

    def draw(self, screen: pygame.Surface, t: float, streak: int, bpm: float) -> None:
        info = self.font.render(f"streak {streak}   {bpm:g} BPM", True, config.GREY)
        screen.blit(info, (config.SCREEN_W - info.get_width() - 20, 20))

        if self._popup is not None:
            judgment, born = self._popup
            if t - born > POPUP_LIFETIME_S:
                self._popup = None
            else:
                color = GRADE_COLORS[judgment.grade]
                name = self.big_font.render(judgment.grade.name, True, color)
                screen.blit(name, (config.SCREEN_W // 2 - name.get_width() // 2, 60))
                if judgment.error_s is not None:
                    detail = self.font.render(format_error(judgment.error_s), True, color)
                    screen.blit(detail, (config.SCREEN_W // 2 - detail.get_width() // 2, 96))
                    # live error bar: | early ... 0 ... late |
                    bar = pygame.Rect(config.SCREEN_W // 2 - 100, 124, 200, 6)
                    pygame.draw.rect(screen, config.GREY, bar, 1)
                    pygame.draw.line(screen, config.GREY, (bar.centerx, 120), (bar.centerx, 134))
                    x = bar.x + error_bar_x(judgment.error_s, bar.width)
                    pygame.draw.circle(screen, color, (x, bar.centery), 5)

    def draw_summary(
        self,
        screen: pygame.Surface,
        errors: list[float],
        counts: dict[Grade, int],
        best_streak: int,
    ) -> None:
        lines = [f"best streak {best_streak}"] + [
            f"{g.name.lower()} {counts[g]}"
            for g in (Grade.PERFECT, Grade.GOOD, Grade.OK, Grade.MISS)
        ]
        for i, text in enumerate(lines):
            surf = self.font.render(text, True, config.DARK)
            screen.blit(surf, (60, 150 + i * 26))

        bins = histogram_bins(errors)
        if errors:
            top = max(bins)
            base_y, h_max, w = 300, 80, 10
            for i, count in enumerate(bins):
                h = 0 if top == 0 else round(count / top * h_max)
                pygame.draw.rect(
                    screen, config.DARK, pygame.Rect(300 + i * (w + 2), base_y - h, w, h)
                )
            label = self.font.render("early   <- timing ->   late", True, config.GREY)
            screen.blit(label, (300, base_y + 8))


__all__ = ["GRADE_COLORS", "Hud", "error_bar_x", "format_error", "histogram_bins"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_hud.py -v`
Expected: 3 PASS

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/game/hud.py tests/test_hud.py
git commit -m "feat: HUD - judgment popups, error bar, session histogram"
```

---
### Task 13: RhythmGame — state machine tying it all together

**Files:**
- Create: `dino_shred/game/game.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: `Dino`, `Ground`, `Obstacle` (Tasks 2/11), `Spawner` (Task 11), `Conductor` (Task 3), `Judge/Grade/Judgment` (Task 8), `CalibrationSession` (Task 9), `Hud` (Task 12), `OnsetEvent` (Task 5).
- Produces: `State` (Enum: `MENU, CALIBRATE, PLAYING, GAME_OVER`); `RhythmGame(bpm: float = 80.0, offset_s: float = 0.0, count_in_beats: int = 4)` with `state: State`, `conductor: Conductor | None`, `on_conductor_change: Callable[[Conductor], None] | None` (hook the app uses to swap the engine's ClickScheduler), `start_playing(t_now: float) -> None`, `start_calibration(t_now: float) -> None`, `handle_onset(ev: OnsetEvent) -> None`, `handle_key(key: int, down: bool, t_now: float) -> None`, `update(t: float) -> None`, `draw(screen: pygame.Surface, t: float) -> None`, `calibration_result: tuple[float, float] | None`, `banner: str` (watchdog messages, set by the app). Task 14 consumes exactly these.

- [x] **Step 1: Write the failing tests**

`tests/test_game.py`:

```python
import pygame

from dino_shred.audio.detect import OnsetEvent
from dino_shred.game.game import RhythmGame, State
from dino_shred.rhythm.judge import Grade


def ev(t: float) -> OnsetEvent:
    return OnsetEvent(t=t, strength=1.0, detector="test")


def start_game(bpm: float = 100.0) -> RhythmGame:
    g = RhythmGame(bpm=bpm)
    g.start_playing(t_now=50.0)
    return g


def test_start_playing_creates_grid_with_lead_in_and_count_in() -> None:
    g = start_game()
    assert g.state is State.PLAYING
    assert g.conductor is not None
    assert g.conductor.t0 == 51.0  # 1 s lead-in
    assert g.judge is not None and g.judge.first_beat == 4  # count-in unjudged


def test_conductor_change_hook_fires() -> None:
    seen = []
    g = RhythmGame(bpm=100.0)
    g.on_conductor_change = seen.append
    g.start_playing(t_now=50.0)
    assert seen == [g.conductor]


def test_onset_jumps_and_judges() -> None:
    g = start_game()
    beat5 = g.conductor.beat_time(5)
    g.update(beat5 - 0.5)
    g.handle_onset(ev(beat5))
    assert not g.dino.on_ground
    assert g.judge.counts[Grade.PERFECT] == 1


def test_missed_beats_counted_on_update() -> None:
    g = start_game()
    g.update(g.conductor.beat_time(8))  # sail past beats 4..7 without chugging
    assert g.judge.counts[Grade.MISS] >= 3


def test_collision_with_grounded_dino_ends_game() -> None:
    g = start_game()
    # walk time up to the first spawned obstacle's beat; dino never jumps
    t = g.conductor.beat_time(4)
    for step in range(120):
        g.update(t - 3.0 + step * 0.025)  # 3 s approach in 25 ms steps
        if g.state is State.GAME_OVER:
            break
    assert g.state is State.GAME_OVER


def test_calibration_flow_produces_offset() -> None:
    g = RhythmGame(bpm=100.0)
    g.start_calibration(t_now=10.0)
    assert g.state is State.CALIBRATE
    for n in range(26):
        g.handle_onset(ev(g.conductor.beat_time(n) + 0.040))
        g.update(g.conductor.beat_time(n) + 0.1)
    assert g.calibration_result is not None
    offset, _spread = g.calibration_result
    assert abs(offset - 0.040) < 0.005
    assert g.state is State.MENU


def test_keyboard_space_acts_as_onset() -> None:
    g = start_game()
    g.handle_key(pygame.K_SPACE, down=True, t_now=g.conductor.beat_time(5))
    assert not g.dino.on_ground
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_game.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/game/game.py`:

```python
"""The rhythm game state machine (spec 3.7).

States: MENU -> CALIBRATE -> MENU -> PLAYING -> GAME_OVER -> (retry) PLAYING.
The game never reads the audio clock itself — the app passes stream time `t`
into update()/draw(), and onsets arrive pre-timestamped. That keeps this whole
module headless-testable with a fake clock.
"""

from collections.abc import Callable
from enum import Enum

import pygame

from dino_shred import config
from dino_shred.audio.detect import OnsetEvent
from dino_shred.game.hud import Hud
from dino_shred.game.objects import Dino, Ground, Obstacle
from dino_shred.game.spawner import Spawner
from dino_shred.rhythm.calibrate import CalibrationSession
from dino_shred.rhythm.conductor import Conductor
from dino_shred.rhythm.judge import Judge, Judgment


class State(Enum):
    MENU = "menu"
    CALIBRATE = "calibrate"
    PLAYING = "playing"
    GAME_OVER = "game_over"


LEAD_IN_S = 1.0


class RhythmGame:
    def __init__(self, bpm: float = 80.0, offset_s: float = 0.0, count_in_beats: int = 4) -> None:
        self.bpm = bpm
        self.offset_s = offset_s
        self.count_in_beats = count_in_beats
        self.state = State.MENU
        self.dino = Dino()
        self.ground = Ground()
        self.hud = Hud()
        self.banner = ""  # watchdog messages, set by the app
        self.conductor: Conductor | None = None
        self.judge: Judge | None = None
        self.spawner: Spawner | None = None
        self.calibration: CalibrationSession | None = None
        self.calibration_result: tuple[float, float] | None = None
        self.obstacles: list[Obstacle] = []
        self.on_conductor_change: Callable[[Conductor], None] | None = None
        self.font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 48)

    # -- state transitions -------------------------------------------------------

    def _new_grid(self, t_now: float) -> Conductor:
        self.conductor = Conductor(t0=t_now + LEAD_IN_S, bpm=self.bpm)
        if self.on_conductor_change is not None:
            self.on_conductor_change(self.conductor)
        return self.conductor

    def start_playing(self, t_now: float) -> None:
        conductor = self._new_grid(t_now)
        self.dino = Dino()
        self.obstacles = []
        self.judge = Judge(conductor, offset_s=self.offset_s, first_beat=self.count_in_beats)
        self.spawner = Spawner(conductor, first_beat=self.count_in_beats)
        self.state = State.PLAYING

    def start_calibration(self, t_now: float) -> None:
        self._new_grid(t_now)
        self.calibration = CalibrationSession(self.conductor)
        self.calibration_result = None
        self.state = State.CALIBRATE

    # -- inputs --------------------------------------------------------------------

    def handle_onset(self, ev: OnsetEvent) -> None:
        if self.state is State.PLAYING and self.judge is not None:
            self.dino.jump()
            judgment: Judgment = self.judge.judge_onset(ev.t)
            self.hud.add(judgment, ev.t)
        elif self.state is State.CALIBRATE and self.calibration is not None:
            self.calibration.add_onset(ev.t)

    def handle_key(self, key: int, down: bool, t_now: float) -> None:
        if key == pygame.K_SPACE and down:
            if self.state is State.MENU:
                self.start_playing(t_now)
            elif self.state is State.GAME_OVER:
                self.start_playing(t_now)
            elif self.state in (State.PLAYING, State.CALIBRATE):
                # keyboard fallback: a synthetic onset at "now"
                self.handle_onset(OnsetEvent(t=t_now, strength=1.0, detector="keyboard"))
        elif key == pygame.K_c and down and self.state is State.MENU:
            self.start_calibration(t_now)
        elif key == pygame.K_DOWN and self.state is State.PLAYING:
            self.dino.duck(down)

    # -- per-frame update ------------------------------------------------------------

    def update(self, t: float) -> None:
        if self.state is State.PLAYING:
            assert self.judge is not None and self.spawner is not None
            self.dino.update()
            self.ground.update(config.PX_PER_SEC / config.FPS)
            self.obstacles.extend(self.spawner.update(t))
            self.obstacles = [o for o in self.obstacles if not o.is_gone(t)]
            for miss in self.judge.sweep_misses(t):
                self.hud.add(miss, t)
            dino_rect = self.dino.rect
            for obs in self.obstacles:
                if dino_rect.colliderect(obs.rect(t)):
                    self.state = State.GAME_OVER
                    return
        elif self.state is State.CALIBRATE:
            assert self.calibration is not None
            if self.calibration.is_complete:
                self.calibration_result = self.calibration.result()
                self.offset_s = self.calibration_result[0]
                self.state = State.MENU

    # -- render ----------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, t: float) -> None:
        screen.fill(config.WHITE)
        self.ground.draw(screen)
        self.dino.draw(screen)
        for obs in self.obstacles:
            obs.draw(screen, t)

        if self.state is State.PLAYING:
            assert self.judge is not None and self.conductor is not None
            self.hud.draw(screen, t, self.judge.streak, self.bpm)
            # beat pulse: flash a dot for 100 ms after each beat
            phase = (t - self.conductor.t0) % self.conductor.period
            if 0 <= phase < 0.1:
                pygame.draw.circle(screen, config.DARK, (40, 40), 10)
        elif self.state is State.MENU:
            self._overlay(screen, "DINO SHRED", "SPACE/chug to play - C to calibrate")
        elif self.state is State.CALIBRATE:
            assert self.calibration is not None
            self._overlay(
                screen, "CALIBRATE",
                f"chug with the click - {self.calibration.hits}/{self.calibration.min_hits}",
            )
        elif self.state is State.GAME_OVER:
            assert self.judge is not None
            self._overlay(screen, "GAME OVER", "SPACE/chug to retry")
            self.hud.draw_summary(
                screen, self.judge.errors, self.judge.counts, self.judge.best_streak
            )

        if self.banner:
            warn = self.font.render(self.banner, True, (207, 34, 46))
            screen.blit(warn, (20, config.SCREEN_H - 30))

    def _overlay(self, screen: pygame.Surface, title: str, subtitle: str) -> None:
        s = pygame.Surface((config.SCREEN_W, config.SCREEN_H), pygame.SRCALPHA)
        s.fill((255, 255, 255, 120))
        screen.blit(s, (0, 0))
        t_surf = self.big_font.render(title, True, config.DARK)
        screen.blit(t_surf, (config.SCREEN_W // 2 - t_surf.get_width() // 2, 100))
        st = self.font.render(subtitle, True, config.GREY)
        screen.blit(st, (config.SCREEN_W // 2 - st.get_width() // 2, 150))


__all__ = ["LEAD_IN_S", "RhythmGame", "State"]
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_game.py -v`
Expected: 8 PASS

- [x] **Step 5: Lint, typecheck, commit**

```bash
uv run ruff check && uv run ty check
git add dino_shred/game/game.py tests/test_game.py
git commit -m "feat: RhythmGame state machine - play, calibrate, judge, collide"
```

---

### Task 14: App wiring — CLI, engine hookup, watchdogs, keyboard-only mode

**Files:**
- Create: `dino_shred/game/app.py`, `dino_shred/__main__.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: everything above; this is the composition root.
- Produces: `build_parser() -> argparse.ArgumentParser`; `main(argv: list[str] | None = None) -> None`; `uv run python -m dino_shred [--bpm 80] [--device N] [--input-channel 2] [--keyboard-only] [--debug-hud]`.

- [x] **Step 1: Write the failing tests**

`tests/test_app.py`:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_app.py -v`
Expected: FAIL — module not found

- [x] **Step 3: Implement**

`dino_shred/game/app.py`:

```python
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
from dino_shred.game.game import RhythmGame, State


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dino-shred", description="Guitar-controlled rhythm trainer")
    p.add_argument("--bpm", type=float, default=80.0)
    p.add_argument("--device", type=int, default=None, help="sounddevice index (default: find M-Track)")
    p.add_argument("--input-channel", type=int, default=2, help="1-based input channel (M-Track instrument = 2)")
    p.add_argument("--keyboard-only", action="store_true", help="no audio: SPACE jumps")
    p.add_argument("--debug-hud", action="store_true", help="show xruns/drops/latency")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    engine: AudioEngine | None = None
    if not args.keyboard_only:
        try:
            engine = AudioEngine(
                detector=EnergyGate(), scheduler=None,
                device=args.device, input_channel=args.input_channel,
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
                        offset_s=offset_s, spread_s=spread_s,
                        date=date.today().isoformat(), device="M-Track Solo",
                        detector="energy", blocksize=config.BLOCKSIZE,
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
                        game.banner = (
                            "no input signal - check gain + macOS Microphone permission"
                        )
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
```

`dino_shred/__main__.py`:

```python
from dino_shred.game.app import main

if __name__ == "__main__":
    main()
```

- [x] **Step 4: Run tests, lint, commit**

Run: `uv run pytest tests/test_app.py -v` — Expected: 2 PASS

```bash
uv run ruff check && uv run ty check && uv run pytest -q
git add dino_shred/game/app.py dino_shred/__main__.py tests/test_app.py
git commit -m "feat: app wiring - CLI, engine hookup, watchdog banners, keyboard mode"
```

- [x] **Step 5: Smoke-test keyboard mode (works without hardware)**

Run: `uv run python -m dino_shred --keyboard-only` — verify: menu shows, SPACE starts,
SPACE jumps on beats (no click audio in this mode — expected), obstacles arrive, judgments
render, collision → GAME OVER with histogram, SPACE retries. Quit window closes cleanly.

- [ ] **Step 6: INTERACTIVE MILESTONE (user + guitar) — not a subagent step**

`uv run python -m dino_shred --bpm 80` from Terminal.app with the M-Track connected.
Checklist: ☐ press C, calibrate with 20+ chugs, offset saved to config.json
☐ play: chugs jump, clicks audible, judgments plausible ☐ deliberately early/late chugs
show negative/positive errors ☐ collision on missed beat ☐ histogram on game over.
Then co-author notebook `notebooks/04-clocks-and-latency.ipynb` (measure callback jitter,
ADC/DAC deltas, calibration distribution on the real rig). Tune `PX_PER_SEC`, BPM feel,
`EnergyGate` thresholds live with the user.

---

### Task 15: Quality gate + docs refresh

**Files:**
- Modify: `CLAUDE.md` (commands + architecture sections)

- [ ] **Step 1: Full quality gate**

```bash
uv run ruff check && uv run ruff format --check && uv run ty check && uv run pytest -q
```
Expected: all clean, all tests pass. Fix anything that isn't — then re-run.

- [ ] **Step 2: Update CLAUDE.md**

In the Commands section add:

```markdown
uv run python -m dino_shred              # guitar rhythm trainer (M-Track required)
uv run python -m dino_shred --keyboard-only   # dev mode without hardware
uv run python -m dino_shred.audio.check  # hardware/latency smoke test
uv run pytest                            # test suite
```

In the Architecture section add one paragraph: the repo now contains two games —
`main.py` (original keyboard tutorial, unchanged) and the `dino_shred/` package
(guitar rhythm trainer: `audio/` duplex-stream engine + onset detection, `rhythm/`
conductor/judge/calibration, `game/` pygame layer). Point to
`docs/superpowers/specs/2026-07-03-guitar-dino-design.md` and `docs/decisions/`.
Note the two invariants: all timing on the stream clock (ADR 0004) and pygame.mixer
never initialized (ADR 0002).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md - rhythm trainer commands and architecture"
```

---

## Plan Self-Review Notes (issues found and fixed inline)

Caught during self-review, corrected above: (1) Task 4 block-equality test used a
length not divisible by 256 and beat times that never actually spanned a block edge;
(2) Task 6 overflow test spaced bursts inside the refractory period; (3) Task 11
spawner test expected beats outside the horizon; (4) Task 14 never persisted the
calibration result (spec 3.6 requires it); (5) `_callback` params needed `Any`
annotations for strict ty.


- Spec coverage: spec §3.1–3.7 map to Tasks 6,4,5,3,8,9/10,11–14; §2 invariants are
  enforced in Tasks 4/6/11; §5 error handling in Tasks 6/7/14; §6 testing satisfied by
  per-task tests + Task 14 smoke test. §3.8 (V2) and M4/M5 detectors are explicitly
  out of scope — separate plans.
- Type consistency verified: `process(frame, t_frame)`, `render(dac_time, out)`,
  `beat_time/nearest_beat/beats_in`, `judge_onset/sweep_misses`, `get_events/take_peak`
  are used with identical signatures at every consumption site.
- Known judgment call: `Ground.update(speed)` is still per-frame-integrated (visual
  dashes only, no gameplay meaning) — acceptable; obstacles are the time-derived ones.

