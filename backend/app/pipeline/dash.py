"""Download a time range from a segmented YouTube stream (DASH, ~2 s per piece, URL has &sq=N).

Long stream VODs are served this way, and yt-dlp's --download-sections can't cut them.
Pieces are self-contained fMP4 fragments, so concatenating them gives a playable file.
"""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.ffmpeg import ffprobe_bin

_SQ_RE = re.compile(r"(sq[=/])0(?=$|[&/])")
MARK = "__SQ__"


def template_from(fragments: list[dict], base_url: str | None = None) -> str | None:
    """URL template for piece N, built from yt-dlp's fragment list."""
    if not fragments:
        return None
    first = fragments[0]
    url = first.get("url") or ((base_url or "") + (first.get("path") or ""))
    if not _SQ_RE.search(url):
        return None
    return _SQ_RE.sub(lambda m: m.group(1) + MARK, url, count=1)


def is_segmented(fmt: dict) -> bool:
    return bool(fmt.get("frag_url"))


def _get(client: httpx.Client, url: str) -> bytes:
    last: Exception | None = None
    for _ in range(4):
        try:
            r = client.get(url)
            r.raise_for_status()
            return r.content
        except httpx.HTTPError as e:
            last = e
    raise RuntimeError(f"segment download failed: {last}")


def probe_start(path: Path) -> float | None:
    out = subprocess.run(
        [ffprobe_bin(), "-v", "error", "-show_entries", "format=start_time", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


_seconds_cache: dict[str, float] = {}


def piece_seconds(fmt: dict, client: httpx.Client, scratch: Path) -> float:
    """Exact seconds per piece, measured from one piece's timestamp in the middle of the stream.

    duration/count is only approximate (e.g. 2.0035 vs a real 2.000), and the error grows to
    minutes deep into a 24h stream, so we measure instead.
    """
    key = fmt["frag_url"].split("&sq=")[0].split("/sq/")[0]
    if key in _seconds_cache:
        return _seconds_cache[key]
    count = int(fmt["frag_count"])
    estimate = float(fmt["frag_seconds"])
    idx = max(1, count // 2)
    probe = scratch / f"probe_{fmt.get('format_id', 'x')}.mp4"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes(_get(client, fmt["frag_url"].replace(MARK, str(idx))))
    t = probe_start(probe)
    probe.unlink(missing_ok=True)
    seconds = t / idx if t and abs(t / idx - estimate) < 0.5 else estimate
    _seconds_cache[key] = seconds
    return seconds


def download_range(fmt: dict, start: float, end: float, out: Path, progress=None, workers: int = 8) -> float:
    """Save pieces covering [start, end] to `out`. Returns the file's real start time in the video."""
    count = int(fmt["frag_count"])
    headers = fmt.get("http_headers") or {}
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client:
        seg = piece_seconds(fmt, client, out.parent)
    first = max(0, int(start // seg))
    last = min(count - 1, int(end // seg) + 1)
    estimate = first * seg

    if not out.exists() or out.stat().st_size == 0:
        urls = [fmt["frag_url"].replace(MARK, str(i)) for i in range(first, last + 1)]
        tmp = out.with_suffix(out.suffix + ".part")
        with httpx.Client(headers=headers, timeout=60, follow_redirects=True) as client, open(tmp, "wb") as f:
            with ThreadPoolExecutor(workers) as pool:
                batch = 64  # keep memory flat: fetch in parallel, write in order
                for i in range(0, len(urls), batch):
                    for data in pool.map(lambda u: _get(client, u), urls[i : i + batch]):
                        f.write(data)
                    if progress:
                        progress(min(1.0, (i + batch) / len(urls)))
        tmp.replace(out)

    # Fragment timestamps are normally absolute (time since stream start); trust them when sane.
    real = probe_start(out)
    if real is not None and abs(real - estimate) < 5:
        return real
    return estimate
