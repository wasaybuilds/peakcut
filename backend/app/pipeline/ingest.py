"""YouTube ingest with yt-dlp.

Long streams are never downloaded in full: we fetch metadata + audio only (small),
find the highlights, then render straight from the remote video stream (see render.py).
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app.config import ROOT_DIR, get_settings
from app.ffmpeg import ffmpeg_bin, media_duration
from app.pipeline import dash

INFO_MAX_AGE = 3 * 3600  # stream URLs expire after ~6h; refresh earlier


class YouTubeBlocked(RuntimeError):
    pass


BOT_HELP = (
    "YouTube is asking to confirm you're not a bot (too many requests from this connection). "
    "Fix: export your YouTube cookies with the 'Get cookies.txt LOCALLY' browser extension and save "
    "the file as backend/tokens/youtube_cookies.txt, then click Retry. Waiting a few hours also works."
)


DEFAULT_COOKIES = ROOT_DIR / "backend" / "tokens" / "youtube_cookies.txt"


def cookies_path() -> Path | None:
    """YTDLP_COOKIES_FILE if set, else backend/tokens/youtube_cookies.txt when present.

    Checked on every call, so dropping the file in place works without a restart.
    """
    configured = get_settings().ytdlp_cookies_file
    p = Path(configured) if configured else DEFAULT_COOKIES
    if not p.is_absolute():
        p = ROOT_DIR / p
    return p if p.is_file() else None


def _base_opts() -> dict:
    s = get_settings()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "js_runtimes": {"node": {}},  # solves YouTube's JS challenges (Node is installed)
        "ffmpeg_location": os.path.dirname(ffmpeg_bin()),
    }
    cookie_file = cookies_path()
    if cookie_file:
        opts["cookiefile"] = str(cookie_file)
    elif s.ytdlp_cookies_from_browser:
        opts["cookiesfrombrowser"] = (s.ytdlp_cookies_from_browser,)
    return opts


def _extract(opts: dict, url: str, **kw) -> dict:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.sanitize_info(ydl.extract_info(url, **kw))
    except yt_dlp.utils.DownloadError as e:
        if "not a bot" in str(e) or "Sign in to confirm" in str(e):
            raise YouTubeBlocked(BOT_HELP) from e
        raise


def job_dir(video_id: str) -> Path:
    d = get_settings().cache_dir / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})")


def _download(opts: dict, url: str) -> None:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        if "not a bot" in str(e) or "Sign in to confirm" in str(e):
            raise YouTubeBlocked(BOT_HELP) from e
        raise


def video_id_for(url: str) -> str:
    """Parse the ID locally (no request to YouTube); fall back to yt-dlp for odd URLs."""
    m = _ID_RE.search(url)
    if m:
        return m.group(1)
    return _extract({**_base_opts(), "extract_flat": True}, url, download=False, process=False)["id"]


def cached_info(video_id: str) -> dict | None:
    path = job_dir(video_id) / "info.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fetch_info(url: str, video_id: str, *, force: bool = False) -> dict:
    """Full metadata incl. formats/heatmap, cached in info.json (refreshed when stale)."""
    path = job_dir(video_id) / "info.json"
    if path.exists() and not force and time.time() - path.stat().st_mtime < INFO_MAX_AGE:
        return json.loads(path.read_text(encoding="utf-8"))
    info = _slim(_extract({**_base_opts(), "skip_download": True, "format": VIDEO_FORMAT}, url, download=False))
    info["_fetched_at"] = time.time()
    path.write_text(json.dumps(info), encoding="utf-8")
    return info


def _slim(info: dict) -> dict:
    """Drop the format/fragment lists: a 24h stream's info is ~900 MB with them, ~50 KB without."""
    drop = {"formats", "thumbnails", "automatic_captions", "subtitles", "requested_downloads"}
    out = {k: v for k, v in info.items() if k not in drop}
    slim_fmts = []
    for f in info.get("requested_formats") or []:
        g = {k: v for k, v in f.items() if k not in ("fragments", "fragment_base_url")}
        frags = f.get("fragments") or []
        tpl = dash.template_from(frags, f.get("fragment_base_url")) if frags else None
        if tpl and info.get("duration"):
            g.update(frag_url=tpl, frag_count=len(frags), frag_seconds=float(info["duration"]) / len(frags))
        slim_fmts.append(g)
    out["requested_formats"] = slim_fmts
    return out


def segmented_formats(info: dict) -> tuple[dict, dict] | None:
    """(video_fmt, audio_fmt) when the stream is served as numbered pieces, else None."""
    fmts = info.get("requested_formats") or []
    if len(fmts) >= 2 and all(dash.is_segmented(f) for f in fmts[:2]):
        return fmts[0], fmts[1]
    return None


def _finished(d: Path, stem: str) -> Path | None:
    for p in d.glob(f"{stem}.*"):
        if p.suffix not in (".part", ".ytdl") and p.stat().st_size > 0:
            return p
    return None


# 48 kbps AAC (itag 139) is plenty for speech-to-text and ~3x smaller than the default track.
AUDIO_FORMAT = "139/ba[ext=m4a][abr<=80]/ba[ext=m4a]/ba/b"


def download_audio(
    url: str,
    video_id: str,
    outdir: Path,
    section: tuple[float, float] | None = None,
    total: float | None = None,
    progress=None,
) -> Path:
    """Audio for transcription.

    The whole track is downloaded with yt-dlp's normal (retrying, resumable) downloader and
    checked for length; a `section` is then cut locally. yt-dlp's own partial download goes
    through a single ffmpeg connection that can silently stop early on long videos.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    if section:
        cut = outdir / "audio.m4a"
        if cut.exists() and cut.stat().st_size > 0:
            return cut

    d = job_dir(video_id)
    full = _finished(d, "audio_full")
    if not full:

        def hook(s):
            if progress and s.get("status") == "downloading":
                size = s.get("total_bytes") or s.get("total_bytes_estimate") or 0
                if size:
                    progress(s.get("downloaded_bytes", 0) / size)

        opts = {
            **_base_opts(),
            "format": AUDIO_FORMAT,
            "outtmpl": str(d / "audio_full.%(ext)s"),
            "progress_hooks": [hook],
            "retries": 10,
            "fragment_retries": 10,
        }
        _download(opts, url)
        full = _finished(d, "audio_full")
        if not full:
            raise RuntimeError("Audio download produced no file.")
        got = media_duration(full)
        if total and got is not None and got < total * 0.97:
            full.unlink(missing_ok=True)
            raise RuntimeError(
                f"Audio download was cut short ({got / 60:.0f} of {total / 60:.0f} min). "
                "Probably a network drop: click Retry."
            )

    if not section:
        return full
    lo, hi = section
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{lo:.3f}", "-t", f"{hi - lo:.3f}", "-i", str(full), "-vn", "-c", "copy", str(cut),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    return cut


# Prefer H.264 (cheap to decode on CPU), cap at 1080p.
VIDEO_FORMAT = (
    "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
)


@dataclass
class StreamSource:
    """Remote (or local) inputs for ffmpeg."""

    video: str
    audio: str | None  # None when video carries audio (muxed format or local file)
    headers: str  # CRLF-joined HTTP headers for ffmpeg, "" for local files
    video_start: float = 0.0  # where the video input begins in the source timeline
    audio_start: float = 0.0


def stream_source(info: dict) -> StreamSource | None:
    """Direct URLs ffmpeg can seek in, or None for segmented streams (use download_section)."""
    fmts = info.get("requested_formats") or [info]
    if any(f.get("protocol") not in ("http", "https") for f in fmts):
        return None  # e.g. long stream VODs served as DASH segments
    headers = fmts[0].get("http_headers") or info.get("http_headers") or {}
    header_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    if len(fmts) >= 2:
        return StreamSource(video=fmts[0]["url"], audio=fmts[1]["url"], headers=header_str)
    return StreamSource(video=fmts[0]["url"], audio=None, headers=header_str)


def _section_paths(video_id: str, start: float, end: float) -> tuple[Path, Path, Path]:
    d = job_dir(video_id) / "sections"
    d.mkdir(exist_ok=True)
    stem = f"{int(start)}_{int(end)}"
    return d / f"{stem}.video.mp4", d / f"{stem}.audio.m4a", d / f"{stem}.json"


def cached_section(video_id: str, start: float, end: float) -> StreamSource | None:
    """A previously downloaded section, without touching the network."""
    v, a, meta = _section_paths(video_id, start, end)
    if not (v.exists() and a.exists()):
        return None
    if not meta.exists():  # older download: read the start times from the files themselves
        vs, as_ = dash.probe_start(v), dash.probe_start(a)
        if vs is None or as_ is None:
            return None
        meta.write_text(json.dumps({"v": vs, "a": as_}), encoding="utf-8")
    m = json.loads(meta.read_text(encoding="utf-8"))
    return StreamSource(video=str(v), audio=str(a), headers="", video_start=m["v"], audio_start=m["a"])


def segmented_section(info: dict, video_id: str, start: float, end: float) -> StreamSource:
    """Local video+audio files for [start, end] of a segmented stream (with ~2 s of slack)."""
    fmts = segmented_formats(info)
    if not fmts:
        raise RuntimeError("not a segmented stream")
    v, a, meta = _section_paths(video_id, start, end)
    v_start = dash.download_range(fmts[0], start - 1, end + 1, v)
    a_start = dash.download_range(fmts[1], start - 1, end + 1, a)
    meta.write_text(json.dumps({"v": v_start, "a": a_start}), encoding="utf-8")
    return StreamSource(video=str(v), audio=str(a), headers="", video_start=v_start, audio_start=a_start)


def download_section(url: str, video_id: str, start: float, end: float) -> Path:
    """Exactly [start, end] of the video as a local file (cut on exact frames)."""
    d = job_dir(video_id) / "sections"
    d.mkdir(exist_ok=True)
    stem = f"{int(start * 1000)}_{int(end * 1000)}"
    done = next((p for p in d.glob(f"{stem}.*") if p.suffix in (".mp4", ".mkv", ".webm")), None)
    if done and done.stat().st_size > 0:
        return done
    opts = {
        **_base_opts(),
        "format": VIDEO_FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(d / f"{stem}.%(ext)s"),
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": True,
    }
    _download(opts, url)
    done = next((p for p in d.glob(f"{stem}.*") if p.suffix in (".mp4", ".mkv", ".webm")), None)
    if not done:
        raise RuntimeError("Section download produced no file.")
    return done


def download_full_video(url: str, video_id: str) -> Path:
    """Fallback when streaming from remote URLs fails (403 etc.)."""
    d = job_dir(video_id)
    existing = d / "video.mp4"
    if existing.exists() and existing.stat().st_size > 0:
        return existing
    opts = {
        **_base_opts(),
        "format": VIDEO_FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": str(d / "video.%(ext)s"),
    }
    _download(opts, url)
    return existing
