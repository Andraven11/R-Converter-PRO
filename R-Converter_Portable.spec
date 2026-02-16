# -*- mode: python ; coding: utf-8 -*-
# R-Converter — Versione Portable (onefile = singolo .exe)
# Build: python _download_ffmpeg_build.py && python -m PyInstaller R-Converter_Portable.spec --noconfirm --clean

from PyInstaller.utils.hooks import collect_all
from pathlib import Path

datas = []
binaries = []
# FFmpeg bundled (eseguire _download_ffmpeg_build.py prima della build)
_ffmpeg_dir = Path("ffmpeg")
if (_ffmpeg_dir / "bin" / "ffmpeg.exe").exists():
    datas.append((str(_ffmpeg_dir), "ffmpeg"))
hiddenimports = [
    'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL.ImageFilter',
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
    a.binaries,
    a.datas,
    [('O', None, 'OPTION'), ('O', None, 'OPTION')],
    name='R-Converter_Portable',
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
    icon='icon.ico',
)
