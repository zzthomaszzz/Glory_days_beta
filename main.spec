# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

pygame_datas, pygame_binaries, pygame_hiddenimports = collect_all('pygame')

a = Analysis(
    ['client\\main.py'],
    pathex=['.'],
    binaries=pygame_binaries,
    datas=pygame_datas,
    hiddenimports=pygame_hiddenimports + [
        'client',
        'client.scene',
        'client.net',
        'client.map_system',
        'client.node',
        'shared',
        'shared.constants',
        'shared.protocol',
        'shared.map_data',
        'shared.items',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['server'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
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
)
