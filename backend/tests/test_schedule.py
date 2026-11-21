from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import db
from app.db import Clip, Job, Publish
from app.publish import publisher, schedule

TIMES = ["09:00", "13:00", "20:30"]


def _local(dt: datetime) -> str:
    return dt.astimezone().strftime("%H:%M")


def test_slots_follow_the_daily_times_in_local_time():
    after = datetime(2026, 11, 21, 6, 0, tzinfo=UTC)
    slots = []
    for s in schedule.slots_after(after, TIMES):
        slots.append(s)
        if len(slots) == 7:
            break
    assert slots[0] > after
    assert slots == sorted(slots) and len(set(slots)) == 7
    assert [_local(s) for s in slots[:3]] in ([TIMES[i % 3] for i in range(k, k + 3)] for k in range(3))
    assert all(_local(s) in TIMES for s in slots)
    assert slots[3] - slots[0] == timedelta(days=1)  # three a day


def test_next_free_slot_skips_taken_and_too_soon_slots():
    now = datetime(2026, 11, 21, 6, 0, tzinfo=UTC)
    slots = schedule.slots_after(now + schedule.LEAD, TIMES)
    first, second = next(slots), next(slots)
    assert schedule.next_free_slot(set(), now, TIMES) == first
    assert schedule.next_free_slot({first}, now, TIMES) == second
    assert schedule.next_free_slot(set(), first - timedelta(minutes=1), TIMES) == second  # 1 min away is too soon


def test_times_are_validated_and_sorted():
    assert schedule.normalise(["21:00", "09:30", "21:00"]) == ["09:30", "21:00"]
    for bad in ([], ["9:00"], ["25:00"], "17:00", ["12:00"] * 1 + [f"{h:02d}:00" for h in range(10)]):
        with pytest.raises(ValueError):
            schedule.normalise(bad)


@pytest.fixture
def engine(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "_engine", eng)
    monkeypatch.setattr(publisher, "get_engine", lambda: eng)
    monkeypatch.setattr(schedule, "get_times", lambda: TIMES)
    sent = []
    monkeypatch.setattr(publisher, "enqueue", sent.append)
    return eng, sent


def _clip(s: Session) -> int:
    job = Job(source_url="https://youtu.be/x")
    s.add(job)
    s.commit()
    clip = Clip(job_id=job.id, start=0, end=30, file_path="a.mp4")
    s.add(clip)
    s.commit()
    return clip.id


def test_tick_posts_due_clips_and_moves_missed_ones(engine):
    eng, sent = engine
    now = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    with Session(eng) as s:
        a, b, c = _clip(s), _clip(s), _clip(s)
        due = Publish(clip_id=a, platform="youtube", scheduled_at=now - timedelta(minutes=5))
        missed = [Publish(clip_id=b, platform=p, scheduled_at=now - timedelta(hours=6)) for p in ("youtube", "instagram")]
        later = Publish(clip_id=c, platform="instagram", scheduled_at=now + timedelta(hours=3))
        s.add_all([due, *missed, later])
        s.commit()
        ids = {"due": due.id, "missed": [m.id for m in missed], "later": later.id}

    publisher.tick(now)

    assert sent == [ids["due"]]
    with Session(eng) as s:
        moved = [s.get(Publish, i).scheduled_at for i in ids["missed"]]
        assert moved[0] == moved[1] > now  # both platforms of the clip stay together
        assert moved[0] != s.get(Publish, ids["later"]).scheduled_at  # didn't land on a taken slot
        assert s.get(Publish, ids["later"]).scheduled_at == now + timedelta(hours=3)
        assert len(s.exec(select(Publish)).all()) == 4


def test_queue_and_mark_posted_endpoints(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    eng, sent = engine
    with Session(eng) as s:
        clip = _clip(s)
    api = TestClient(app)  # no `with`: skips startup, so no worker threads

    r = api.post(f"/api/clips/{clip}/publish", json={"platforms": ["youtube", "instagram"], "when": "queue"})
    assert r.status_code == 200 and r.json()["scheduled_at"] and sent == []
    assert api.post(f"/api/clips/{clip}/publish", json={"platforms": ["youtube"], "when": "queue"}).status_code == 400
    q = api.get("/api/schedule").json()
    assert q["times"] == TIMES and len(q["queue"]) == 1
    assert sorted(q["queue"][0]["platforms"]) == ["instagram", "youtube"]
    assert q["next_slot"] != q["queue"][0]["scheduled_at"]

    # marking as posted is refused while it's queued there
    assert api.post(f"/api/clips/{clip}/posted", json={"platform": "youtube"}).status_code == 400

    assert api.post(f"/api/clips/{clip}/queue/now").json()["started"] == 2 and len(sent) == 2
    with Session(eng) as s:
        assert all(p.scheduled_at is None for p in s.exec(select(Publish)).all())
        for p in s.exec(select(Publish)).all():
            s.delete(p)
        s.commit()

    api.post(f"/api/clips/{clip}/publish", json={"platforms": ["instagram"], "when": "queue"})
    assert api.delete(f"/api/clips/{clip}/queue").json()["removed"] == 1
    assert api.get("/api/schedule").json()["queue"] == []

    bad = api.post(f"/api/clips/{clip}/posted", json={"platform": "instagram", "url": "instagram.com/reel/x"})
    assert bad.status_code == 400
    ok = api.post(f"/api/clips/{clip}/posted", json={"platform": "instagram", "url": "https://www.instagram.com/reel/x/"})
    assert ok.status_code == 200
    with Session(eng) as s:
        (p,) = s.exec(select(Publish)).all()
        assert p.status == "done" and p.post_url.endswith("/reel/x/")
    assert api.delete(f"/api/clips/{clip}/posted/instagram").json()["removed"] == 1
