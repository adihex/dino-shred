# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Dino Shred is a Chrome Dino clone written in pygame, built as a teaching project. There are two synchronized artifacts of the *same* game:

- `main.py` — the complete, runnable reference implementation (single file, ~377 lines).
- `dino_shred.ipynb` — a step-by-step tutorial notebook that builds the identical game cell by cell with prose explanations of each game-dev concept.

When changing game behavior, keep both in sync: a change to a class in `main.py` should be mirrored in the corresponding notebook cell, and vice versa. The notebook's markdown cells document the "why" behind each design decision.

## Commands

Dependencies are managed with **uv** (see `uv.lock`); the project targets **Python 3.13**.

```bash
uv sync                    # install deps (incl. dev group) into .venv
uv run python main.py      # run the game
uv run python -m dino_shred              # guitar rhythm trainer (M-Track required)
uv run python -m dino_shred --keyboard-only   # dev mode without hardware
uv run python -m dino_shred.audio.check  # hardware/latency smoke test
uv run pytest                            # run test suite
uv run ruff check          # lint
uv run ruff check --fix    # lint + autofix
uv run ruff format         # format
uv run ty check            # type check (ty = Astral's type checker, used instead of mypy/pyright)
```

The keyboard trainer is verified manually. The guitar rhythm trainer has a test suite under `tests/` which runs headlessly using dummy SDL drivers (see `tests/conftest.py`).

### Docker

`requirements.txt` is a stub — the Dockerfile installs from it but it contains no pinned deps, so add `pygame` before relying on the container. Docker also has no display by default, so the GUI won't render without X forwarding.

```bash
docker compose up --build                                   # run in container
docker compose -f compose.debug.yaml up --build             # run with debugpy on :5678 (waits for debugger attach)
```

## Architecture

The repository contains two games:
1. The original single-file `main.py` keyboard tutorial (unchanged).
2. The `dino_shred/` package guitar rhythm trainer.

The `dino_shred/` package is structured into three main modules:
- **`audio/`**: Manages the full-duplex `sounddevice` stream engine and onset detection (EnergyGate).
- **`rhythm/`**: Handles the conductor timing math (ADR 0004), calibration (ADR 0001), and timing judgment (±30/60/100 ms).
- **`game/`**: Implements the Pygame loop, HUD rendering, and composition/state-machine wiring.

Design invariants:
- **Stream clock conduction (ADR 0004)**: All gameplay and rendering are derived from the master stream clock time, avoiding drift.
- **No `pygame.mixer` (ADR 0002)**: All sound is synthesized and played directly via the duplex audio stream.

See specs in `docs/superpowers/specs/2026-07-03-guitar-dino-design.md` and ADRs in `docs/decisions/`.

`main.py` is organized around the classic game-loop structure and is intentionally didactic — comments reference six "core principles" (game loop, state machine, input abstraction, AABB collision, object pooling, progressive difficulty).

- **`main()`** — the game loop: `INPUT → UPDATE → RENDER` at a fixed 60 FPS (`clock.tick(FPS)`). Pumps events into `Game.handle_event`, then `Game.update`, then `Game.draw`.
- **`Game`** — the orchestrator and state machine. `self.state` is a string: `"START" | "PLAYING" | "GAME_OVER"`. `update`/`draw` short-circuit when not `PLAYING`. Owns the dino, ground, obstacle list, score/high-score, and spawn timing. `_spawn_obstacle` gates obstacle variety by score (cacti early, birds added at 200/500). `handle_event` maps raw keys to intents (start/retry/jump/duck) — the game never reads keys outside this method.
- **`Dino`** — player. Fixed x-position (world scrolls past it); `vy` + `GRAVITY` drive jump physics; ducking swaps to a shorter hitbox. `jump()`/`duck()` are the input-abstraction surface.
- **`Obstacle`** — scrolling cactus/bird. 4 variants via the `SIZES`/`BIRD_Y_OFFSETS` dicts; moves left each frame; culled when off-screen.
- **`Ground`** — scrolling dashed line drawn with a shifting offset (visual trick; nothing actually moves).

Each game object follows the same `update()` / `draw(screen)` / `rect` (hitbox) trio. Collision is AABB via `pygame.Rect.colliderect`, with hitboxes padded inward a few px to feel forgiving. All art is `pygame.draw` primitives — no sprite assets — so swapping in sprite sheets would happen inside each `draw`.

### Tuning the game

Gameplay feel lives in the `ALL_CAPS` constants at the top of `main.py` (gravity, jump velocity, speeds, spawn windows). Difficulty scales with score: `speed` ramps from `BASE_SPEED` toward `MAX_SPEED`, and spawn windows tighten as speed rises.

## Conventions

- Ruff enforces 100-char lines, double quotes, and the lint set `E,F,I,N,W,UP,B,SIM,C4`. Format/lint-fix on save is configured in `.vscode/settings.json`.
- Type checking is **strict** and done with `ty` (not Pylance) — the VS Code Python language server is disabled in favor of it. Keep full type annotations on new code (the existing code is fully annotated).
