# -*- mode: python ; coding: utf-8 -*-
# Whale Pet (DSH-integrated edition) PyInstaller build config -- onefile single exe
from PyInstaller.utils.hooks import collect_all

datas = [('sprites', 'sprites')]
binaries = []
hiddenimports = ['win32com.client']   # SAPI voice (dynamic COM, avoid missing collection)

for pkg in ('psutil', 'requests', 'win32com', 'edge_tts', 'aiohttp'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    ['desktop_pet.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='desktop-pet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
