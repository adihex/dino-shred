# GUI Launcher Packaging Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Package the guitar rhythm trainer into a standalone macOS `.app` bundle using PyInstaller so it runs in windowed GUI mode without a background terminal console showing.

**Architecture:** We will add `pyinstaller` to the dev dependencies, write a custom PyInstaller `.spec` configuration file setting `console=False`, compile it via `pyinstaller`, and verify the resulting bundle executes.

**Tech Stack:** Python 3.13, uv, PyInstaller 6.11

---

### Task 1: Add pyinstaller dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Check existing dependencies**
Let's verify our dependencies are clean.

**Step 2: Add PyInstaller**
Run:
```bash
uv add --dev pyinstaller
```
Expected: `pyproject.toml` is updated with `pyinstaller` in the dev dependencies, and `uv.lock` is updated.

**Step 3: Commit**
```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pyinstaller to dev dependencies"
```

---

### Task 2: Create PyInstaller Spec configuration

**Files:**
- Create: `dino_shred.spec`

**Step 1: Write the Spec file**
Create the spec file:
```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['dino_shred/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['sounddevice'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dino-shred',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False to run in windowed GUI mode without Terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dino-shred',
)

app = BUNDLE(
    coll,
    name='Dino Shred.app',
    icon=None,
    bundle_identifier='com.dino-shred.game',
)
```

**Step 2: Commit**
```bash
git add dino_shred.spec
git commit -m "feat: create pyinstaller spec configuration"
```

---

### Task 3: Build and verify standalone bundle

**Files:**
- Verify build: `dist/Dino Shred.app`

**Step 1: Run PyInstaller build**
Run:
```bash
uv run pyinstaller --noconfirm dino_shred.spec
```
Expected: PyInstaller compiles the app and generates a folder structure under `dist/dino-shred` and a package `dist/Dino Shred.app`.

**Step 2: Verify launcher works headlessly**
Run the compiled binary under dummy settings to ensure no missing dependencies or package resolution errors occur:
```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./dist/Dino\ Shred.app/Contents/MacOS/dino-shred --keyboard-only
```
Wait for 2 seconds and check that it launches successfully without crashing.

**Step 3: Commit build configurations and update CLAUDE.md**
We do not check in the compiled binary `dist/` or `build/` (already ignored by `.gitignore`), but we commit any final build setups if modified.
```bash
git commit -m "feat: build and verify standalone macOS app bundle"
```
