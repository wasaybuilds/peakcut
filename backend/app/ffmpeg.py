"""Locate ffmpeg and pick the fastest working H.264 encoder.

Encoder-probe idea adapted from MoneyPrinterTurbo (MIT, see NOTICE).
"""

import os
import shutil
import subprocess
import sys
from functools import lru_cache

from app.config import get_settings


class FFmpegMissing(RuntimeError):
    pass


def _fresh_windows_path() -> str:
    """PATH as stored in the registry: winget installs don't reach already-open shells."""
    if sys.platform != "win32":
        return ""
    import winreg

    parts = []
    for root, key in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(root, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    parts.append(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"))
    return os.pathsep.join(parts)


@lru_cache
def _find(tool: str) -> str:
    path = shutil.which(tool) or shutil.which(tool, path=_fresh_windows_path())
    if not path:
        raise FFmpegMissing(f"{tool} not found on PATH. Run scripts/setup.ps1.")
    path = os.path.realpath(path)
    # Some libraries (yt-dlp's section downloader) only search PATH, so make sure it's there.
    folder = os.path.dirname(path)
    if folder.lower() not in (p.lower() for p in os.environ.get("PATH", "").split(os.pathsep)):
        os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    return path


def ffmpeg_bin() -> str:
    return _find("ffmpeg")


def ffprobe_bin() -> str:
    return _find("ffprobe")


def ffmpeg_version() -> str | None:
    try:
        out = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-version"], capture_output=True, text=True, timeout=15
        )
        return out.stdout.splitlines()[0] if out.stdout else None
    except (FFmpegMissing, OSError, subprocess.SubprocessError):
        return None


def _encoder_works(encoder: str) -> bool:
    """Encode one tiny frame; listing the encoder isn't enough (QSV needs the driver)."""
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1",
        "-c:v", encoder, "-f", "null", "-",
    ]  # fmt: skip
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def media_duration(path) -> float | None:
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


@lru_cache
def video_encoder() -> str:
    pref = get_settings().video_encoder
    if pref != "auto":
        return pref
    return "h264_qsv" if _encoder_works("h264_qsv") else "libx264"
