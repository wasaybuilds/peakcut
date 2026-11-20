from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db import Clip, Job, Publish, get_session
from app.pipeline import ingest, metadata
from app.publish import instagram, publisher, youtube

router = APIRouter(prefix="/api")

PLATFORMS = ("youtube", "instagram")


# ---- accounts --------------------------------------------------------------------


@router.get("/accounts")
def accounts():
    return {"youtube": youtube.status(), "instagram": instagram.status()}


@router.post("/accounts/youtube/connect")
def youtube_connect():
    try:
        youtube.start_connect()
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "message": "A Google sign-in page is opening in your browser."}


@router.delete("/accounts/youtube")
def youtube_disconnect():
    youtube.disconnect()
    return {"ok": True}


class IGToken(BaseModel):
    access_token: str = Field(min_length=20)


@router.post("/accounts/instagram")
def instagram_connect(body: IGToken):
    try:
        data = instagram.connect(body.access_token)
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


class MetaUpdate(BaseModel):
    youtube: YTMeta
    instagram: IGMeta
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
    clip.meta = meta
    session.add(clip)
    session.commit()
    return meta


# ---- publishing -----------------------------------------------------------------


class PublishBody(BaseModel):
    platforms: list[str]


@router.post("/clips/{clip_id}/publish")
def publish_clip(clip_id: int, body: PublishBody, session: Session = Depends(get_session)):
    clip = session.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Clip not found")
    if not clip.file_path:
        raise HTTPException(400, "This clip hasn't finished rendering.")
    wanted = [p for p in body.platforms if p in PLATFORMS]
    if not wanted:
        raise HTTPException(400, "Pick YouTube and/or Instagram.")
    created = []
    for platform in wanted:
        busy = session.exec(select(Publish).where(Publish.clip_id == clip_id, Publish.platform == platform,
                                                  Publish.status.in_(["pending", "uploading"]))).first()  # fmt: skip
        if busy:
            continue
        pub = Publish(clip_id=clip_id, platform=platform)
        session.add(pub)
        session.commit()
        session.refresh(pub)
        publisher.enqueue(pub.id)
        created.append(pub.id)
    return {"ok": True, "queued": created}


@router.get("/clips/{clip_id}/publishes")
def clip_publishes(clip_id: int, session: Session = Depends(get_session)):
    return session.exec(select(Publish).where(Publish.clip_id == clip_id).order_by(Publish.id.desc())).all()
