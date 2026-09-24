# Design Doc: Standalone macOS App Bundle for Guitar Dino

**Date:** 2026-07-03  
**Status:** Approved  

---

## 1. Goal
Provide a native macOS `.app` bundle (`Dino Shred.app`) that users can launch by double-clicking. The app should launch the Pygame game directly and run in windowed GUI mode without a background terminal console opening.

---

## 2. Technical Approach
We will use **PyInstaller** to compile the application and bundle all dependencies.

### 2.1 Dependencies
We will add `pyinstaller` as a dev dependency in the `pyproject.toml` so that it is managed by `uv`.

### 2.2 Spec Configuration (`dino_shred.spec`)
We will create a custom spec file containing:
* `Analysis`: Points to `dino_shred/__main__.py` as the entrypoint. Collects all packages (pygame, numpy, sounddevice).
* `EXE`: Configured with `console=False` (which prevents the terminal window from showing on launch).
* `COLLECT` / `BUNDLE`: Sets up `Dino Shred.app` as the final bundle target on macOS.

### 2.3 PortAudio Handling
`sounddevice` contains its own pre-compiled `libportaudio.dylib` inside its Python package folder. PyInstaller's built-in hooks for `sounddevice` should automatically detect and collect this. We will verify that this binary is correctly bundled.

---

## 3. Verification Plan
* **Build Verification:** Run `uv run pyinstaller --noconfirm dino_shred.spec` and verify it compiles without errors.
* **Launch Verification:** Run the compiled binary under dummy settings to ensure no missing module/binary import errors:
  ```bash
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./dist/Dino\ Shred.app/Contents/MacOS/dino-shred --keyboard-only
  ```
