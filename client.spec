# -*- mode: python ; coding: utf-8 -*-
from sys import platform

block_cipher = None
datas = [
    ('icon.ico', '.')  # Adjust the path according to your project structure
]

a = Analysis(
    ['racehub_client_python/client.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['pystray', 'PIL'],
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
    name='RaceHubClient',
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
    entitlements_file=None,
    icon='icon.ico' if platform == 'win32' else None,
    version='racehub_client_python/racehubclient_version.txt',
)

# Only create an .app bundle if on MacOS
if platform == "darwin":
    app = BUNDLE(
        exe,
        name='RaceHubClient.app',
        icon=None,
        bundle_identifier=None
    )
