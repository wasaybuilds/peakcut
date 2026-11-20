"""Cover images for Reels/Shorts: one frame of the clip with the hook set large in the middle.

Instagram's profile grid shows only the centre 3:4 of a 9:16 Reel (1080x1440 of 1080x1920),
so the text sits inside that band; the burned-in hook at the top of the clip would be cropped.
"""

import subprocess
from pathlib import Path

from app.ffmpeg import ffmpeg_bin
from app.pipeline.captions import PINK, WHITE

W, H = 1080, 1920
GRID_TOP, GRID_BOTTOM = 240, 1680  # the 3:4 band the profile grid keeps


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def cover_ass(text: str) -> str:
    """Hook text centred in the grid band, in the same pink box style as the clip's hook."""
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cover,Arial Black,104,{WHITE},{WHITE},{PINK},&H00000000,-1,0,0,0,100,100,0,0,3,26,0,5,110,110,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Cover,,0,0,0,,{{\\pos({W // 2},{(GRID_TOP + GRID_BOTTOM) // 2})}}{_esc(text).upper()}
"""


def make_cover(video: Path, out: Path, at: float, text: str) -> Path:
    """Write a 1080x1920 JPEG cover from `video` at `at` seconds (relative to the clip)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.07:saturation=1.1"
    if text.strip():
        ass = out.with_suffix(".cover.ass")
        ass.write_text(cover_ass(text), encoding="utf-8")
        vf += f",subtitles={ass.name}"
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{max(0.0, at):.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", vf, "-q:v", "2", out.name,
    ]  # fmt: skip
    # cwd = output dir so the subtitles filter gets a plain relative filename (Windows paths)
    proc = subprocess.run(cmd, cwd=out.parent, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"cover failed: {proc.stderr.strip()[-400:]}")
    return out


def default_at(duration: float) -> float:
    """A frame a third of the way in: past the opening hook overlay, usually mid-action."""
    return round(max(0.0, min(duration - 0.2, duration * 0.35)), 1)
