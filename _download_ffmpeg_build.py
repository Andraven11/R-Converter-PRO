"""
Script per scaricare FFmpeg essentials prima della build PyInstaller.
Esegui: python _download_ffmpeg_build.py
Output: ffmpeg/bin/ffmpeg.exe, ffmpeg/bin/ffprobe.exe
"""
import os
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
SCRIPT_DIR = Path(__file__).parent
DEST_DIR = SCRIPT_DIR / "ffmpeg"
ZIP_PATH = DEST_DIR / "ffmpeg.zip"

def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    print("Download FFmpeg essentials...")
    req = Request(URL, headers={"User-Agent": "R-Converter-Build/2.0"})
    with urlopen(req, timeout=120) as resp:
        data = resp.read()
    ZIP_PATH.write_bytes(data)
    print("Estrazione...")
    bin_dir = DEST_DIR / "bin"
    bin_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for name in zf.namelist():
            if name.endswith("ffmpeg.exe") or name.endswith("ffprobe.exe"):
                # Nome in zip: ffmpeg-7.x-essentials_build/bin/ffmpeg.exe
                dest_name = Path(name).name
                dest_path = bin_dir / dest_name
                with zf.open(name) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
    ZIP_PATH.unlink(missing_ok=True)
    print("OK:", bin_dir / "ffmpeg.exe")

if __name__ == "__main__":
    main()
