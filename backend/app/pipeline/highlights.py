"""Pick viral moments: transcript + signal hot spots -> LLM -> clean, non-overlapping windows."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import get_settings
from app.llm.client import chat_json
from app.pipeline.signals import hot_spots

log = logging.getLogger(__name__)

CHUNK_SECONDS = 20 * 60

SYSTEM = """You are a top short-form video editor for gaming content (GTA 6 streams and videos).
You pick the moments that will go viral as YouTube Shorts / Instagram Reels / TikToks.
Great clips: funny reactions, chaos, unexpected events, fails, insane plays, rage, big reveals,
wholesome or shocking moments, quotable lines. Each clip must make sense on its own and hook the
viewer in the first 2 seconds. Avoid starting a clip on graphic violence.
Reply with JSON only."""

USER_TMPL = """Video: "{title}" by {channel}
Window: {win_start}s to {win_end}s of a {duration}s video.

Transcript (seconds, absolute):
{transcript}

Hot spots (loud moments / most-replayed parts; strong hint something happens there):
{spots}

Pick up to {k} of the best clips in this window. Rules:
- each clip {min_len}-{max_len} seconds long, inside the window
- start just before the setup (a sentence start), end right after the payoff
- score 0-100 = how likely it goes viral; be strict, filler moments score < 40

Return exactly:
{{"clips": [{{"start": <sec>, "end": <sec>, "score": <int>,
  "title": "<= 60 chars, curiosity-driven, no clickbait lies",
  "hook": "<= 6 words, punchy on-screen text",
  "reason": "<one sentence why this works>",
  "hashtags": ["#gta6", "..."]}}]}}"""


@dataclass
class Highlight:
    start: float
    end: float
    score: int
    title: str
    hook: str
    reason: str
    hashtags: list[str] = field(default_factory=list)


def _fmt_transcript(segments: list[dict], a: float, b: float) -> str:
    lines = [f"[{s['s']:.1f}-{s['e']:.1f}] {s['text']}" for s in segments if a <= s["s"] < b]
    return "\n".join(lines) or "(no speech in this window)"


def _fmt_spots(spots: list[dict]) -> str:
    if not spots:
        return "(none)"
    return "\n".join(f"t={s['t']}s loudness +{s['loud_db']}dB replay-heat {s['heat']}" for s in spots)


def snap(h: Highlight, segments: list[dict], duration: float, min_len: int, max_len: int) -> Highlight:
    """Snap to sentence boundaries (within 3s) and enforce length/bounds."""
    starts = [s["s"] for s in segments if h.start - 3 <= s["s"] <= h.start + 1]
    ends = [s["e"] for s in segments if h.end - 1 <= s["e"] <= h.end + 3]
    start = min(starts, key=lambda x: abs(x - h.start)) if starts else h.start
    end = min(ends, key=lambda x: abs(x - h.end)) if ends else h.end
    start = max(0.0, start - 0.15)  # tiny lead-in so the first word isn't clipped
    end = min(duration, end + 0.3)
    if end - start > max_len:
        end = start + max_len
    if end - start < min_len:
        pad = (min_len - (end - start)) / 2
        start, end = max(0.0, start - pad), min(duration, end + pad)
    h.start, h.end = round(start, 2), round(end, 2)
    return h


def dedupe(items: list[Highlight], max_overlap: float = 0.3) -> list[Highlight]:
    kept: list[Highlight] = []
    for h in sorted(items, key=lambda x: x.score, reverse=True):
        ok = True
        for k in kept:
            inter = max(0.0, min(h.end, k.end) - max(h.start, k.start))
            if inter / min(h.end - h.start, k.end - k.start) > max_overlap:
                ok = False
                break
        if ok:
            kept.append(h)
    return kept


def _coerce(c: dict) -> Highlight | None:
    try:
        start, end = float(c["start"]), float(c["end"])
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start:
        return None
    tags = c.get("hashtags") or []
    return Highlight(
        start=start,
        end=end,
        score=int(float(c.get("score", 50))),
        title=str(c.get("title", ""))[:100],
        hook=str(c.get("hook", ""))[:60],
        reason=str(c.get("reason", ""))[:300],
        hashtags=[t if t.startswith("#") else f"#{t}" for t in tags if isinstance(t, str)][:10],
    )


def _signal_only(signals: dict, lo: float, hi: float, duration: float, count: int, min_len: int) -> list[Highlight]:
    """No usable speech: build windows around the strongest loudness/heat peaks."""
    spots = hot_spots(signals, lo, hi, top=count, min_gap=min_len * 2)
    out = []
    for i, s in enumerate(sorted(spots, key=lambda x: x["score"], reverse=True), 1):
        a = max(0.0, s["t"] - 10)
        out.append(Highlight(a, min(duration, a + max(min_len, 25)), int(min(99, 40 + s["score"] * 20)),
                             f"GTA 6 moment #{i}", "WAIT FOR IT", "Loudness/replay peak", ["#gta6"]))  # fmt: skip
    return out


def find(
    info: dict,
    transcript: dict,
    signals: dict,
    workdir: Path,
    count: int,
    span: tuple[float, float] | None = None,
    progress=None,
) -> list[Highlight]:
    """`span` limits the search to part of a long video (absolute seconds)."""
    path = workdir / f"highlights_{count}.json"
    if path.exists():
        return [Highlight(**h) for h in json.loads(path.read_text(encoding="utf-8"))]

    s = get_settings()
    duration = float(info.get("duration") or 0)
    lo, hi = span or (0.0, duration)
    segments = transcript["segments"]
    speech_words = len(transcript["words"])

    if speech_words < 40:
        result = _signal_only(signals, lo, hi, duration, count, s.min_clip_seconds)
    else:
        n_windows = max(1, int(-(-(hi - lo) // CHUNK_SECONDS)))
        per_window = max(3, -(-count * 2 // n_windows))  # over-sample, then keep the best
        candidates: list[Highlight] = []
        for i in range(n_windows):
            a, b = lo + i * CHUNK_SECONDS, min(hi, lo + (i + 1) * CHUNK_SECONDS)
            prompt = USER_TMPL.format(
                title=info.get("title", ""), channel=info.get("channel", ""),
                win_start=int(a), win_end=int(b), duration=int(duration),
                transcript=_fmt_transcript(segments, a, b), spots=_fmt_spots(hot_spots(signals, a, b)),
                k=per_window, min_len=s.min_clip_seconds, max_len=s.max_clip_seconds,
            )  # fmt: skip
            try:
                data, used = chat_json(SYSTEM, prompt)
                raw = data.get("clips", []) if isinstance(data, dict) else data
                for c in raw:
                    h = _coerce(c)
                    if h and a - 5 <= h.start < b:
                        candidates.append(snap(h, segments, duration, s.min_clip_seconds, s.max_clip_seconds))
                log.info("window %d/%d: %d clips via %s", i + 1, n_windows, len(raw), used)
            except Exception as e:
                log.warning("highlight window %d failed: %s", i, e)
            if progress:
                progress((i + 1) / n_windows)
        result = dedupe(candidates)[:count]
        if not result:
            result = _signal_only(signals, lo, hi, duration, count, s.min_clip_seconds)

    result.sort(key=lambda h: h.score, reverse=True)
    path.write_text(json.dumps([asdict(h) for h in result], ensure_ascii=False), encoding="utf-8")
    return result
