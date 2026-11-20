import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from app import worker
from app.config import get_settings
from app.db import Clip, Job, Publish, get_session
from app.pipeline.captions import STYLES
from app.pipeline.render import LAYOUTS

router = APIRouter(prefix="/api")

YT_RE = re.compile(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/", re.I)


class CreateJob(BaseModel):
    url: str
    clip_count: int = Field(default=8, ge=1, le=20)
    layout: str = "zoom_fill"
    caption_style: str = "bold_pop"


@router.get("/options")
def options():
    return {"layouts": list(LAYOUTS), "caption_styles": list(STYLES)}


@router.post("/jobs")
def create_job(body: CreateJob, session: Session = Depends(get_session)):
    url = body.url.strip()
    if not YT_RE.match(url):
        raise HTTPException(400, "Paste a YouTube link (youtube.com or youtu.be).")
    if body.layout not in LAYOUTS or body.caption_style not in STYLES:
        raise HTTPException(400, "Unknown layout or caption style.")
    job = Job(source_url=url, options=body.model_dump(exclude={"url"}))
    session.add(job)
    session.commit()
    session.refresh(job)
    worker.enqueue(job.id)
    return job


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job).order_by(Job.id.desc()).limit(30)).all()
    ids = [j.id for j in jobs]
    counts = dict(
        session.exec(select(Clip.job_id, func.count(Clip.id)).where(Clip.job_id.in_(ids)).group_by(Clip.job_id)).all()
    )
    return [{**j.model_dump(), "clip_count": counts.get(j.id, 0)} for j in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    clips = session.exec(select(Clip).where(Clip.job_id == job_id).order_by(Clip.score.desc())).all()
    pubs = session.exec(select(Publish).where(Publish.clip_id.in_([c.id for c in clips])).order_by(Publish.id)).all()
    by_clip: dict[int, dict] = {}
    for p in pubs:  # latest attempt per platform wins
        by_clip.setdefault(p.clip_id, {})[p.platform] = p.model_dump(
            include={"id", "platform", "status", "post_url", "error", "created_at"}
        )
    return {"job": job, "clips": [{**c.model_dump(), "publishes": by_clip.get(c.id, {})} for c in clips]}


class FacecamBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0.02, le=1)
    h: float = Field(gt=0.02, le=1)


class Rerender(BaseModel):
    layout: str
    caption_style: str | None = None
    facecam: FacecamBox | None = None  # set = use this box; omit = keep / auto-detect
    redetect: bool = False


@router.post("/jobs/{job_id}/rerender")
def rerender(job_id: int, body: Rerender, session: Session = Depends(get_session)):
    """Re-render every clip with a new layout / face cam box. Earlier steps come from cache."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("queued", "running"):
        raise HTTPException(409, "This job is still running.")
    if body.layout not in LAYOUTS or (body.caption_style and body.caption_style not in STYLES):
        raise HTTPException(400, "Unknown layout or caption style.")
    opts = dict(job.options or {})
    opts["layout"] = body.layout
    if body.caption_style:
        opts["caption_style"] = body.caption_style
    if body.facecam:
        b = body.facecam
        opts["facecam"] = {"x": b.x, "y": b.y, "w": min(b.w, 1 - b.x), "h": min(b.h, 1 - b.y)}
    elif body.redetect:
        opts.pop("facecam", None)
    job.options = opts
    renders = get_settings().renders_dir
    for clip in session.exec(select(Clip).where(Clip.job_id == job_id)):
        for rel in (clip.file_path, clip.thumb_path):
            if rel:  # remove the old render (+ its .ass/.jpg siblings)
                for sibling in (renders / rel).parent.glob(Path(rel).stem + "*"):  # .mp4/.ass/.jpg + _cover.jpg
                    sibling.unlink(missing_ok=True)
        clip.layout = body.layout
        if body.caption_style:
            clip.caption_style = body.caption_style
        clip.file_path = None
        clip.thumb_path = None
        session.add(clip)
    job.status, job.error, job.step, job.progress = "queued", None, None, 0.65
    session.add(job)
    session.commit()
    worker.enqueue(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status in ("queued", "running"):
        return {"ok": True}  # already in the queue; don't run it twice
    job.status, job.error = "queued", None
    session.add(job)
    session.commit()
    worker.enqueue(job_id)
    return {"ok": True}
