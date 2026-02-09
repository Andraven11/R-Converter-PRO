# -*- mode: python ; coding: utf-8 -*-
# R-Converter — Versione Installer (onedir)
# Build: pyinstaller R-Converter.spec --noconfirm --clean

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'PIL', 'PIL.Image', 'PIL.ImageTk',
    'cv2', 'numpy',
    'windnd', 'windnd.windnd',
    'ctypes', 'ctypes.wintypes',
]

# Raccogli tutto il pacchetto windnd (necessario per drag & drop)
tmp_ret = collect_all('windnd')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'pytest', 'setuptools', 'wheel', 'pip'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    exclude_binaries=True,
    name='R-Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='R-Converter',
)
