"""One ffmpeg pass per clip: seek -> 9:16 layout -> ASS captions -> loudness norm -> H.264.

Input can be remote YouTube streams (frame-accurate input seeking, nothing big downloaded)
or a local file.
"""

import subprocess
from pathlib import Path

from app.ffmpeg import ffmpeg_bin, video_encoder
from app.pipeline.ingest import StreamSource

W, H = 1080, 1920

LAYOUTS = {
    # name: foreground width before cropping to 1080 (None = special chain)
    "zoom_fill": 1620,  # 16:9 zoomed 1.5x on blurred background - best default for gameplay
    "blur_fill": 1080,  # whole frame visible, blurred background top/bottom
    "center_crop": None,  # fill the screen, sides cut off
    "facecam_split": None,  # streamer's face cam on top, gameplay below
}


class RenderError(RuntimeError):
    pass


def facecam_height(box: dict, src_aspect: float = 16 / 9) -> int:
    """Height of the face cam panel: keeps the cam's own shape, within sensible limits."""
    cam_aspect = (box["w"] * src_aspect) / max(box["h"], 1e-3)  # width / height in pixels
    h = int(W / cam_aspect)
    return max(480, min(900, h)) // 2 * 2


def _facecam_chain(box: dict, src_aspect: float, tail: str) -> str:
    top = facecam_height(box, src_aspect)
    bot = H - top
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    return (
        "[0:v]split=2[fc][gp];"
        f"[fc]crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={W}:{top}:force_original_aspect_ratio=increase,"
        f"crop={W}:{top}[top];"
        f"[gp]scale=-2:{bot}:force_original_aspect_ratio=increase,crop={W}:{bot}[bot];"
        f"[top][bot]vstack=inputs=2,{tail}"
    )


def _video_chain(
    layout: str, ass_name: str, pix_fmt: str, facecam: dict | None = None, src_aspect: float = 16 / 9
) -> str:
    tail = f"fps=30,subtitles={ass_name},format={pix_fmt}[v]"
    if layout == "facecam_split" and facecam:
        return _facecam_chain(facecam, src_aspect, tail)
    if layout == "facecam_split":
        layout = "zoom_fill"  # no face cam found -> best fallback
    fw = LAYOUTS.get(layout, LAYOUTS["zoom_fill"])
    if fw is None:
        return f"[0:v]scale=-2:{H},crop={W}:{H},{tail}"
    return (
        "[0:v]split=2[bgi][fgi];"
        f"[bgi]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
        f"boxblur=8:2,scale={W}:{H},eq=brightness=-0.12:saturation=1.2[bg];"
        f"[fgi]scale={fw}:-2,crop='min(iw,{W})':'min(ih,{H})'[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{tail}"
    )


def _encoder_args(encoder: str) -> tuple[list[str], str]:
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", "22", "-preset", "medium"], "nv12"
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"], "yuv420p"


def _inputs(src: StreamSource | Path, start: float) -> tuple[list[str], str]:
    if isinstance(src, Path):
        return ["-ss", f"{start:.3f}", "-i", str(src)], "0:a?"
    remote = src.video.startswith("http")
    net = ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"] if remote else []
    if src.headers:
        net = ["-headers", src.headers, *net]
    args = [*net, "-ss", f"{max(0.0, start - src.video_start):.3f}", "-i", src.video]
    if src.audio:
        args += [*net, "-ss", f"{max(0.0, start - src.audio_start):.3f}", "-i", src.audio]
        return args, "1:a"
    return args, "0:a?"


def render_clip(
    src: StreamSource | Path,
    start: float,
    end: float,
    ass_text: str,
    out_path: Path,
    *,
    layout: str = "zoom_fill",
    encoder: str | None = None,
    facecam: dict | None = None,
    src_aspect: float = 16 / 9,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = out_path.with_suffix(".ass")
    ass_path.write_text(ass_text, encoding="utf-8")

    encoder = encoder or video_encoder()
    enc_args, pix_fmt = _encoder_args(encoder)
    in_args, audio_map = _inputs(src, start)
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        *in_args,
        "-t", f"{end - start:.3f}",
        "-filter_complex", _video_chain(layout, ass_path.name, pix_fmt, facecam, src_aspect),
        "-map", "[v]", "-map", audio_map,
        *enc_args,
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart",
        out_path.name,
    ]  # fmt: skip
    # cwd = output dir so the subtitles filter gets a plain relative filename
    # (Windows drive-letter paths need painful escaping inside filtergraphs).
    proc = subprocess.run(cmd, cwd=out_path.parent, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0 or not out_path.exists():
        if encoder != "libx264":  # QSV can fail on odd inputs/drivers -> software fallback
            return render_clip(src, start, end, ass_text, out_path, layout=layout, encoder="libx264",
                               facecam=facecam, src_aspect=src_aspect)  # fmt: skip
        raise RenderError(proc.stderr.strip()[-1500:] or "ffmpeg failed")
    return out_path


def thumbnail(video: Path, at: float = 1.0) -> Path:
    thumb = video.with_suffix(".jpg")
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=540:-2", "-q:v", "4", str(thumb),
    ]  # fmt: skip
    subprocess.run(cmd, check=False, capture_output=True, timeout=60)
    return thumb
