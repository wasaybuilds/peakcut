"""Upload queue (its own thread, so posting never blocks rendering).

Posts with no `scheduled_at` go out right away. Scheduled ones (see schedule.py) are picked up by
a ticker when their slot arrives. If the laptop was off or asleep through a slot, the post moves
to the next free slot instead of everything going out in one burst when it wakes up.
"""

import logging
import queue
import threading
import time
import traceback
from datetime import timedelta

from sqlmodel import Session, select

from app.config import get_settings
from app.db import Clip, Publish, get_engine
from app.publish import instagram, schedule, youtube

log = logging.getLogger(__name__)

_queue: "queue.Queue[int]" = queue.Queue()
_queued: set[int] = set()  # ids waiting in _queue, so the ticker never adds one twice
_lock = threading.Lock()
_started = False

TICK_SECONDS = 20
GRACE = timedelta(minutes=30)  # a slot missed by more than this moves to the next free slot


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
            cover_at = (meta.get("cover") or {}).get("at")
            url = instagram.publish(path, (meta.get("instagram") or {}).get("caption", clip.title), cover_at=cover_at)
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
            with _lock:
                _queued.discard(pid)
            _queue.task_done()


def enqueue(pub_id: int) -> None:
    with _lock:
        if pub_id in _queued:
            return
        _queued.add(pub_id)
    _queue.put(pub_id)


def taken_slots(session: Session) -> set:
    rows = session.exec(select(Publish.scheduled_at).where(Publish.status == "pending",
                                                            Publish.scheduled_at.is_not(None))).all()  # fmt: skip
    return set(rows)


def tick(now=None) -> None:
    """Send due posts to the upload thread; move posts whose slot was missed to the next free one."""
    now = now or schedule.utcnow()
    with Session(get_engine()) as s:
        due = s.exec(select(Publish).where(Publish.status == "pending", Publish.scheduled_at.is_not(None),
                                           Publish.scheduled_at <= now).order_by(Publish.scheduled_at)).all()  # fmt: skip
        moved: dict = {}  # old slot -> new slot, so a clip's platforms stay together
        for p in due:
            if now - p.scheduled_at <= GRACE:
                enqueue(p.id)
                continue
            if p.scheduled_at not in moved:
                moved[p.scheduled_at] = schedule.next_free_slot(taken_slots(s) | set(moved.values()), now)
            log.info("publish %s missed its slot %s, moved to %s", p.id, p.scheduled_at, moved[p.scheduled_at])
            p.scheduled_at = moved[p.scheduled_at]
            s.add(p)
        s.commit()


def _ticker() -> None:
    while True:
        try:
            tick()
        except Exception:
            log.error("schedule tick failed: %s", traceback.format_exc())
        time.sleep(TICK_SECONDS)


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
            elif p.scheduled_at is None:
                enqueue(p.id)  # "post now" that never started; scheduled ones are the ticker's job
        s.commit()
    threading.Thread(target=_ticker, name="publish-schedule", daemon=True).start()
