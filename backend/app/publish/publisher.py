"""Upload queue (its own thread, so posting never blocks rendering)."""

import logging
import queue
import threading
import traceback

from sqlmodel import Session, select

from app.config import get_settings
from app.db import Clip, Publish, get_engine
from app.publish import instagram, youtube

log = logging.getLogger(__name__)

_queue: "queue.Queue[int]" = queue.Queue()
_started = False


def _set(pub_id: int, **fields) -> None:
    with Session(get_engine()) as s:
        p = s.get(Publish, pub_id)
        for k, v in fields.items():
            setattr(p, k, v)
        s.add(p)
        s.commit()


def run(pub_id: int) -> None:
    with Session(get_engine()) as s:
        pub = s.get(Publish, pub_id)
        if not pub or pub.status not in ("pending", "failed"):
            return
        clip = s.get(Clip, pub.clip_id)
        platform = pub.platform
        meta = dict(clip.meta or {})
        rel = clip.file_path
    _set(pub_id, status="uploading", error=None)
    try:
        if not rel:
            raise RuntimeError("This clip hasn't been rendered yet.")
        path = get_settings().renders_dir / rel
        if platform == "youtube":
            yt = meta.get("youtube") or {}
            url = youtube.upload(path, yt.get("title", clip.title), yt.get("description", ""),
                                 yt.get("tags") or meta.get("hashtags") or [], yt.get("privacy", "public"))  # fmt: skip
        elif platform == "instagram":
            url = instagram.publish(path, (meta.get("instagram") or {}).get("caption", clip.title))
        else:
            raise RuntimeError(f"unknown platform {platform}")
        _set(pub_id, status="done", post_url=url)
    except Exception as e:
        log.error("publish %s failed: %s", pub_id, traceback.format_exc())
        _set(pub_id, status="failed", error=str(e)[:1000])


def _loop() -> None:
    while True:
        pid = _queue.get()
        try:
            run(pid)
        finally:
            _queue.task_done()


def enqueue(pub_id: int) -> None:
    _queue.put(pub_id)


def start() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="publisher", daemon=True).start()
    with Session(get_engine()) as s:
        for p in s.exec(select(Publish).where(Publish.status.in_(["pending", "uploading"]))):
            if p.status == "uploading":
                # interrupted mid-upload: it may or may not have gone through, so don't re-post blindly
                p.status, p.error = "failed", "Interrupted by a restart. Check the platform, then retry if needed."
                s.add(p)
            else:
                enqueue(p.id)
        s.commit()
