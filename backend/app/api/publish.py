from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.config import get_settings
from app.db import Clip, Job, Publish, get_session
from app.pipeline import cover, ingest, metadata
from app.publish import instagram, publisher, schedule, tiktok, youtube

router = APIRouter(prefix="/api")

PLATFORMS = ("youtube", "instagram", "tiktok")


# ---- accounts --------------------------------------------------------------------


@router.get("/accounts")
def accounts():
    return {"youtube": youtube.status(), "instagram": instagram.status(), "tiktok": tiktok.status()}


@router.post("/accounts/youtube/connect")
def youtube_connect():
    try:
        youtube.start_connect()
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "message": "A Google sign-in page is opening in your browser."}


@router.post("/accounts/tiktok/connect")
def tiktok_connect():
    try:
        tiktok.start_connect()
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "message": "A TikTok sign-in page is opening in your browser."}


@router.delete("/accounts/tiktok")
def tiktok_disconnect():
    tiktok.disconnect()
    return {"ok": True}


@router.delete("/accounts/youtube")
def youtube_disconnect():
    youtube.disconnect()
    return {"ok": True}


class IGToken(BaseModel):
    access_token: str = Field(min_length=20)
    account_id: str | None = Field(default=None, max_length=40)  # only needed if lookup fails (EAA tokens)


@router.post("/accounts/instagram")
def instagram_connect(body: IGToken):
    try:
        data = instagram.connect(body.access_token, body.account_id)
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "username": data.get("username")}


@router.delete("/accounts/instagram")
def instagram_disconnect():
    instagram.disconnect()
    return {"ok": True}


# ---- captions -------------------------------------------------------------------


def _write_captions(session: Session, clips: list[Clip], job: Job) -> None:
    info = ingest.cached_info(job.video_id) or {"title": job.title, "channel": job.channel, "webpage_url": job.source_url}
    words = metadata.find_words(job.video_id, clips[0].start) if job.video_id else []
    metas = metadata.generate(
        [{"title": c.title, "hook_text": c.hook_text, "reason": c.reason, "start": c.start, "end": c.end,
          "meta": c.meta} for c in clips], info, words,
    )  # fmt: skip
    for c, m in zip(clips, metas, strict=True):
        c.meta = m
        session.add(c)
    session.commit()


@router.post("/jobs/{job_id}/captions")
def job_captions(job_id: int, session: Session = Depends(get_session)):
    """(Re)write AI captions + hashtags for every clip in a job (works for older jobs too)."""
    job = session.get(Job, job_id)
    clips = session.exec(select(Clip).where(Clip.job_id == job_id).order_by(Clip.id)).all()
    if not job or not clips:
        raise HTTPException(404, "Job or clips not found")
    _write_captions(session, list(clips), job)
    return {"ok": True}


@router.post("/clips/{clip_id}/captions")
def clip_captions(clip_id: int, session: Session = Depends(get_session)):
    clip = session.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    _write_captions(session, [clip], session.get(Job, clip.job_id))
    session.refresh(clip)
    return clip.meta


class YTMeta(BaseModel):
    title: str = Field(max_length=100)
    description: str = Field(max_length=5000)
    privacy: str = Field(default="public", pattern="^(public|unlisted|private)$")


class IGMeta(BaseModel):
    caption: str = Field(max_length=2200)


class TTMeta(BaseModel):
    caption: str = Field(max_length=2200)


class MetaUpdate(BaseModel):
    youtube: YTMeta
    instagram: IGMeta
    tiktok: TTMeta | None = None
    hashtags: list[str] = []


@router.put("/clips/{clip_id}/meta")
def update_meta(clip_id: int, body: MetaUpdate, session: Session = Depends(get_session)):
    clip = session.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    meta = dict(clip.meta or {})
    tags = [t if t.startswith("#") else f"#{t}" for t in body.hashtags if t.strip()]
    meta["hashtags"] = tags
    meta["youtube"] = {**body.youtube.model_dump(), "tags": [t.lstrip("#") for t in tags]}
    meta["instagram"] = body.instagram.model_dump()
    if body.tiktok:
        meta["tiktok"] = body.tiktok.model_dump()
    clip.meta = meta
    session.add(clip)
    session.commit()
    return meta


# ---- cover image ----------------------------------------------------------------


class CoverBody(BaseModel):
    at: float | None = Field(default=None, ge=0)  # seconds into the clip; default keeps the current frame
    text: str | None = Field(default=None, max_length=80)  # default keeps the current text


@router.post("/clips/{clip_id}/cover")
def make_cover(clip_id: int, body: CoverBody, session: Session = Depends(get_session)):
    """Create or redo a clip's cover: one frame plus the hook text, inside the grid's 3:4 band."""
    clip = session.get(Clip, clip_id)
    if not clip or not clip.file_path:
        raise HTTPException(404, "This clip hasn't been rendered yet.")
    renders = get_settings().renders_dir
    video = renders / clip.file_path
    length = clip.end - clip.start
    prev = (clip.meta or {}).get("cover") or {}
    at = body.at if body.at is not None else prev.get("at", cover.default_at(length))
    at = min(float(at), max(0.0, length - 0.2))
    text = body.text if body.text is not None else prev.get("text", clip.hook_text or clip.title)
    try:
        out = cover.make_cover(video, video.with_name(f"{video.stem}_cover.jpg"), at, text)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e
    clip.meta = {**(clip.meta or {}), "cover": {"path": out.relative_to(renders).as_posix(), "at": at, "text": text}}
    session.add(clip)
    session.commit()
    return clip.meta["cover"]


# ---- publishing -----------------------------------------------------------------


class PublishBody(BaseModel):
    platforms: list[str]
    when: str = Field(default="now", pattern="^(now|queue)$")  # queue = next free posting slot


def _clip_or_404(session: Session, clip_id: int) -> Clip:
    clip = session.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    return clip


def _pending(session: Session, clip_id: int, platform: str | None = None):
    q = select(Publish).where(Publish.clip_id == clip_id, Publish.status.in_(["pending", "uploading"]))
    if platform:
        q = q.where(Publish.platform == platform)
    return session.exec(q).all()


@router.post("/clips/{clip_id}/publish")
def publish_clip(clip_id: int, body: PublishBody, session: Session = Depends(get_session)):
    clip = _clip_or_404(session, clip_id)
    if not clip.file_path:
        raise HTTPException(400, "This clip hasn't finished rendering.")
    wanted = [p for p in body.platforms if p in PLATFORMS]
    if not wanted:
        raise HTTPException(400, "Pick at least one of YouTube, Instagram or TikTok.")
    when = None
    if body.when == "queue":
        if any(p.scheduled_at for p in _pending(session, clip_id)):
            raise HTTPException(400, "This clip is already in the queue.")
        when = schedule.next_free_slot(publisher.taken_slots(session))
    created = []
    for platform in wanted:
        if _pending(session, clip_id, platform):
            continue  # already uploading or waiting
        pub = Publish(clip_id=clip_id, platform=platform, scheduled_at=when)
        session.add(pub)
        session.commit()
        session.refresh(pub)
        if when is None:
            publisher.enqueue(pub.id)
        created.append(pub.id)
    return {"ok": True, "queued": created, "scheduled_at": schedule.iso(when)}


@router.delete("/clips/{clip_id}/queue")
def unqueue_clip(clip_id: int, session: Session = Depends(get_session)):
    """Take a clip out of the posting queue (uploads already running are left alone)."""
    rows = [p for p in _pending(session, clip_id) if p.status == "pending" and p.scheduled_at]
    for p in rows:
        session.delete(p)
    session.commit()
    return {"ok": True, "removed": len(rows)}


@router.post("/clips/{clip_id}/queue/now")
def post_queued_now(clip_id: int, session: Session = Depends(get_session)):
    rows = [p for p in _pending(session, clip_id) if p.status == "pending" and p.scheduled_at]
    for p in rows:
        p.scheduled_at = None
        session.add(p)
    session.commit()
    for p in rows:
        publisher.enqueue(p.id)
    return {"ok": True, "started": len(rows)}


class PostedBody(BaseModel):
    platform: str = Field(pattern="^(youtube|instagram|tiktok)$")
    url: str | None = Field(default=None, max_length=500)


@router.post("/clips/{clip_id}/posted")
def mark_posted(clip_id: int, body: PostedBody, session: Session = Depends(get_session)):
    """Record a post made outside PeakCut (for example from the Instagram app)."""
    _clip_or_404(session, clip_id)
    url = (body.url or "").strip() or None
    if url and not url.startswith(("https://", "http://")):
        raise HTTPException(400, "The link should start with https://")
    if _pending(session, clip_id, body.platform):
        raise HTTPException(400, "This clip is queued or uploading there. Remove it from the queue first.")
    pub = Publish(clip_id=clip_id, platform=body.platform, status="done", post_url=url)
    session.add(pub)
    session.commit()
    return {"ok": True}


@router.delete("/clips/{clip_id}/posted/{platform}")
def unmark_posted(clip_id: int, platform: str, session: Session = Depends(get_session)):
    """Forget that a clip was posted on a platform. Doesn't touch the post itself."""
    rows = session.exec(select(Publish).where(Publish.clip_id == clip_id, Publish.platform == platform,
                                              Publish.status.in_(["sent", "done", "failed"]))).all()  # fmt: skip
    for p in rows:
        session.delete(p)
    session.commit()
    return {"ok": True, "removed": len(rows)}


# ---- posting schedule -----------------------------------------------------------


class ScheduleBody(BaseModel):
    times: list[str]


def _queue_view(session: Session) -> list[dict]:
    rows = session.exec(select(Publish).where(Publish.status.in_(["pending", "uploading"]),
                                              Publish.scheduled_at.is_not(None)).order_by(Publish.scheduled_at)).all()  # fmt: skip
    items: dict[tuple, dict] = {}
    for p in rows:
        key = (p.clip_id, p.scheduled_at)
        if key not in items:
            clip = session.get(Clip, p.clip_id)
            if not clip:
                continue
            items[key] = {"clip_id": clip.id, "job_id": clip.job_id, "title": clip.title, "thumb_path": clip.thumb_path,
                          "scheduled_at": schedule.iso(p.scheduled_at), "platforms": [], "uploading": False}  # fmt: skip
        items[key]["platforms"].append(p.platform)
        items[key]["uploading"] |= p.status == "uploading"
    return list(items.values())


@router.get("/schedule")
def get_schedule(session: Session = Depends(get_session)):
    return {"times": schedule.get_times(), "queue": _queue_view(session),
            "next_slot": schedule.iso(schedule.next_free_slot(publisher.taken_slots(session)))}  # fmt: skip


@router.put("/schedule")
def put_schedule(body: ScheduleBody, session: Session = Depends(get_session)):
    """Change the daily posting times. Clips already queued keep their slots."""
    try:
        schedule.set_times(body.times)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return get_schedule(session)


@router.get("/clips/{clip_id}/publishes")
def clip_publishes(clip_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Publish).where(Publish.clip_id == clip_id).order_by(Publish.id.desc())).all()
