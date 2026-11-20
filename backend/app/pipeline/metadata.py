"""AI-written post text: YouTube title/description/tags and Instagram caption + hashtags.

Structure of clip.meta (same keys the publishers read):
  {"hashtags": [...], "youtube": {"title", "description", "tags", "privacy"}, "instagram": {"caption"}}
"""

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.llm.client import chat_json

log = logging.getLogger(__name__)

BASE_TAGS = ["#gta6", "#gtavi", "#gta6gameplay", "#gaming"]

SYSTEM = """You write captions for viral gaming Shorts and Reels (GTA 6 clips).
Your text is punchy, specific to the moment, and sounds like a real clipper account, not a brand.
No clickbait lies, no ALL CAPS sentences, at most 2 emojis per caption. Reply with JSON only."""

USER_TMPL = """Game: GTA 6. Creator in the clips: {creator}. Source video: "{source_title}".

Clips:
{clips}

For EACH clip write:
- yt_title: <= 70 chars, curiosity + the specific moment, no hashtags
- ig_caption: 1-2 short lines. First line is the hook. End with a question or a call to action
  (e.g. "Would you have done this?" / "Follow for daily GTA 6 clips").
- hashtags: 8-12 tags. 3-4 broad (#gta6 #gtavi #gaming ...), 4-6 about THIS moment
  (e.g. #policechase #gta6funny), 1 for the creator (e.g. #{creator_tag}).

Return exactly: {{"clips": [{{"n": 1, "yt_title": "...", "ig_caption": "...", "hashtags": ["#..."]}}]}}"""


def _norm_tags(tags, creator_tag: str) -> list[str]:
    out = []
    for t in list(tags or []) + BASE_TAGS + ([f"#{creator_tag}"] if creator_tag else []):
        if not isinstance(t, str):
            continue
        t = "#" + "".join(ch for ch in t.lstrip("#") if ch.isalnum() or ch == "_")
        if len(t) > 1 and t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out[:14]


def compose(title: str, ig_caption: str, tags: list[str], creator: str, source_url: str, privacy: str) -> dict:
    yt_tags = tags[:5] + ["#shorts"]
    return {
        "hashtags": tags,
        "youtube": {
            "title": f"{title} #shorts"[:100],
            "description": f"{ig_caption}\n\n🎥 Credit: {creator} — {source_url}\n\n{' '.join(yt_tags)}"[:5000],
            "tags": [t.lstrip("#") for t in tags],
            "privacy": privacy,
        },
        "instagram": {"caption": f"{ig_caption}\n\n🎥 {creator} (YouTube)\n.\n{' '.join(tags + ['#reels', '#gamingreels'])}"[:2200]},
    }


def _excerpt(words: list[dict], start: float, end: float, limit: int = 450) -> str:
    text = " ".join(w["w"] for w in words if start <= w["s"] < end)
    return (text[:limit] + "…") if len(text) > limit else text


def generate(clips: list[dict], info: dict, words: list[dict]) -> list[dict]:
    """clips: [{"title","hook_text","reason","start","end","meta"}]. Returns a meta dict per clip."""
    creator = info.get("channel") or (info.get("uploader_id") or "").lstrip("@") or "the creator"
    creator_tag = "".join(ch for ch in creator if ch.isalnum())
    src = info.get("webpage_url", "")
    lines = []
    for n, c in enumerate(clips, 1):
        lines.append(f'{n}) title: "{c["title"]}" | hook: "{c["hook_text"]}" | why it works: {c["reason"]}\n'
                     f'   transcript: "{_excerpt(words, c["start"], c["end"])}"')  # fmt: skip
    by_n: dict[int, dict] = {}
    try:
        data, used = chat_json(SYSTEM, USER_TMPL.format(creator=creator, source_title=info.get("title", ""),
                                                        clips="\n".join(lines), creator_tag=creator_tag))  # fmt: skip
        for item in (data.get("clips", []) if isinstance(data, dict) else data) or []:
            try:
                by_n[int(item.get("n"))] = item
            except (TypeError, ValueError):
                continue
        log.info("captions for %d clips via %s", len(by_n), used)
    except Exception as e:  # no LLM available -> template captions below
        log.warning("caption generation failed: %s", e)

    out = []
    for n, c in enumerate(clips, 1):
        item = by_n.get(n, {})
        old = c.get("meta") or {}
        privacy = (old.get("youtube") or {}).get("privacy", "public")
        title = (item.get("yt_title") or c["title"] or "GTA 6 moment").strip()
        caption = (item.get("ig_caption") or c["title"]).strip()
        tags = _norm_tags(item.get("hashtags") or old.get("hashtags"), creator_tag)
        out.append(compose(title, caption, tags, creator, src, privacy))
    return out


def find_words(video_id: str, start: float) -> list[dict]:
    """Transcript words for a clip, from whichever cached analysis range contains it."""
    base = get_settings().cache_dir / video_id
    for t in sorted(base.rglob("transcript.json"), key=lambda p: len(str(p))):
        words = json.loads(Path(t).read_text(encoding="utf-8")).get("words", [])
        if words and words[0]["s"] - 5 <= start <= words[-1]["e"] + 5:
            return words
    return []
