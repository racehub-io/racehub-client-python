# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from sys import platform

allhiddenimports = collect_submodules('pyarrow.vendored')

allhiddenimports += ['traceback']

block_cipher = None

a = Analysis(
    ['racehub_client_python/worker.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=allhiddenimports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RaceHubWorker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,  # add your entitlements file here if you're code-signing
    icon='icon.ico' if platform == 'win32' else None,
    version='racehub_client_python/racehubworker_version.txt',
)

# Only create an .app bundle if on MacOS
if platform == "darwin":
    app = BUNDLE(
        exe,
        name='RaceHubWorker.app',
        icon=None,
        bundle_identifier=None
    )
