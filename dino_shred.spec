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
