from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import db
from app.config import get_settings
from app.db import Clip, Job, Publish


@pytest.fixture
def setup(tmp_path, monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "_engine", eng)
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    from app.main import app

    return eng, tmp_path, TestClient(app)  # no `with`: skips startup, so no worker threads


def _job(s: Session, vid: str, n_clips: int = 1) -> tuple[int, list[int]]:
    job = Job(source_url=f"https://youtu.be/{vid}", video_id=vid, status="done")
    s.add(job)
    s.commit()
    ids = []
    for i in range(n_clips):
        clip = Clip(job_id=job.id, start=0, end=30, file_path=f"{vid}/job{job.id}_clip{i + 1:02d}.mp4")
        s.add(clip)
        s.commit()
        ids.append(clip.id)
    return job.id, ids


def test_delete_job_removes_its_rows_and_files_but_keeps_shared_ones(setup):
    eng, data, api = setup
    vid = "QdBZY2fkU-0"
    with Session(eng) as s:
        a, a_clips = _job(s, vid, 2)
        b, _ = _job(s, vid)
        s.add(Publish(clip_id=a_clips[0], platform="youtube", status="done", post_url="https://youtube.com/shorts/x"))
        s.commit()
    renders, cache = data / "renders" / vid, data / "cache" / vid
    renders.mkdir(parents=True)
    cache.mkdir(parents=True)
    for name in (f"job{a}_clip01.mp4", f"job{a}_clip01_cover.jpg", f"job{b}_clip01.mp4", f"job{a}0_clip01.mp4"):
        (renders / name).write_bytes(b"x")
    (cache / "info.json").write_text("{}")

    assert api.delete(f"/api/jobs/{a}").json() == {"ok": True}
    assert sorted(p.name for p in renders.iterdir()) == [f"job{a}0_clip01.mp4", f"job{b}_clip01.mp4"]  # job1_ isn't job10_
    assert cache.exists()  # job b still uses this video
    with Session(eng) as s:
        assert s.get(Job, a) is None and not s.exec(select(Publish)).all()
        assert [c.job_id for c in s.exec(select(Clip)).all()] == [b]

    (renders / f"job{a}0_clip01.mp4").unlink()
    assert api.delete(f"/api/jobs/{b}").status_code == 200
    assert not renders.exists() and not cache.exists()  # last job for the video: everything goes


def test_delete_job_refuses_running_and_queued(setup):
    eng, _, api = setup
    with Session(eng) as s:
        a, clips = _job(s, "abcdefghijk")
        running = Job(source_url="https://youtu.be/zzzzzzzzzzz", video_id="zzzzzzzzzzz", status="running")
        s.add_all([running, Publish(clip_id=clips[0], platform="instagram", scheduled_at=datetime.now(UTC))])
        s.commit()
        running_id = running.id
    assert api.delete(f"/api/jobs/{running_id}").status_code == 400
    assert "queue" in api.delete(f"/api/jobs/{a}").json()["detail"]
    assert api.delete("/api/jobs/9999").status_code == 404
