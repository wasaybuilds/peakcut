"""SQLite models: a Job is one source URL; it produces Clips; Clips get Publishes."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_url: str
    video_id: str | None = None
    title: str | None = None
    channel: str | None = None
    duration: float | None = None
    status: JobStatus = JobStatus.queued
    step: str | None = None  # current pipeline step
    progress: float = 0.0  # 0..1
    error: str | None = None
    options: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Clip(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    start: float
    end: float
    score: int = 0
    title: str = ""
    hook_text: str = ""
    reason: str = ""
    layout: str = "blur_fill"
    caption_style: str = "bold_pop"
    file_path: str | None = None
    thumb_path: str | None = None
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))  # titles/hashtags per platform
    created_at: datetime = Field(default_factory=_now)


class Publish(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    clip_id: int = Field(foreign_key="clip.id", index=True)
    platform: str  # youtube | instagram
    status: str = "pending"  # pending | uploading | sent (TikTok inbox) | done | failed
    scheduled_at: datetime | None = None
    post_url: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.ensure_dirs()
        _engine = create_engine(
            f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False}
        )
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session():
    with Session(get_engine()) as session:
        yield session
