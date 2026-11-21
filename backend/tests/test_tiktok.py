import hashlib
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.config import get_settings
from app.publish import tiktok


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._data


OK = {"code": "ok", "message": ""}


@pytest.fixture
def keys(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "tiktok_client_key", "ck_test")
    monkeypatch.setattr(s, "tiktok_client_secret", "cs_test")
    monkeypatch.setattr(tiktok, "TOKEN", tmp_path / "tiktok.json")
    return s


def test_pkce_is_hex_sha256_and_auth_url_has_the_documented_params(keys):
    verifier, challenge = tiktok._pkce()
    assert 43 <= len(verifier) <= 128
    assert challenge == hashlib.sha256(verifier.encode()).hexdigest()
    q = parse_qs(urlparse(tiktok.auth_url("st", challenge)).query)
    assert q["client_key"] == ["ck_test"] and q["response_type"] == ["code"]
    assert q["scope"] == ["user.info.basic,video.upload"] and q["code_challenge_method"] == ["S256"]
    assert q["redirect_uri"] == [f"http://localhost:{keys.tiktok_redirect_port}/callback/"]
    assert "client_secret" not in q  # never in the browser URL


def test_exchange_checks_state_and_scope_then_saves_tokens(keys, monkeypatch):
    posted = {}

    def fake_post(url, data=None, timeout=None, **kw):
        posted.update(data)
        return FakeResponse({"access_token": "act", "refresh_token": "rft", "expires_in": 7200,
                             "refresh_expires_in": 15552000, "open_id": "oid", "scope": "user.info.basic,video.upload"})  # fmt: skip

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse({"data": {"user": {"display_name": "mostreplayed"}}, "error": OK}))
    cb = "http://localhost:8788/callback/?code=abc%2A&scopes=video.upload&state=good"

    with pytest.raises(RuntimeError, match="state"):
        tiktok.exchange(cb.replace("good", "evil"), "good", "ver")
    data = tiktok.exchange(cb, "good", "ver")
    assert posted["code"] == "abc*" and posted["code_verifier"] == "ver" and posted["grant_type"] == "authorization_code"
    assert data["display_name"] == "mostreplayed" and tiktok.status()["connected"]

    with pytest.raises(RuntimeError, match="cancel|not completed"):
        tiktok.exchange("http://localhost:8788/callback/?error=access_denied&state=good", "good", "ver")


def test_exchange_refuses_a_token_without_video_upload(keys, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(
        {"access_token": "a", "refresh_token": "r", "open_id": "o", "scope": "user.info.basic"}))
    with pytest.raises(RuntimeError, match="video.upload"):
        tiktok.exchange("http://x/callback/?code=c&state=s", "s", "v")
    assert not tiktok.TOKEN.exists()


def test_expired_access_token_refreshes_and_keeps_the_rotated_refresh_token(keys, monkeypatch):
    tiktok._save({"access_token": "old", "refresh_token": "r1", "expires_at": time.time() - 10,
                  "refresh_expires_at": time.time() + 1000, "open_id": "o", "display_name": "me"})  # fmt: skip
    sent = {}

    def fake_post(url, data=None, timeout=None, **kw):
        sent.update(data)
        return FakeResponse({"access_token": "new", "refresh_token": "r2", "expires_in": 7200, "refresh_expires_in": 9999})

    monkeypatch.setattr(httpx, "post", fake_post)
    data = tiktok._token()
    assert sent["grant_type"] == "refresh_token" and sent["refresh_token"] == "r1"
    assert data["access_token"] == "new" and tiktok._load()["refresh_token"] == "r2"
    assert tiktok._load()["display_name"] == "me"


def test_chunks_follow_tiktok_rules():
    assert tiktok.chunks(13_200_000) == (13_200_000, 1)
    size, count = tiktok.chunks(95_000_000)
    assert size == 10_000_000 and count == 9  # last chunk carries the extra 5 MB
    assert 5_000_000 <= size <= 64_000_000


class FakeClient:
    """Stands in for httpx.Client during an inbox upload."""

    def __init__(self, statuses, put_status=201):
        self.calls, self.statuses, self.put_status = [], list(statuses), put_status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/inbox/video/init/"):
            return FakeResponse({"data": {"publish_id": "v_inbox_file~1", "upload_url": "https://up.tiktok/x?sig=1"}, "error": OK})
        return FakeResponse({"data": {"status": self.statuses.pop(0), "fail_reason": "frame_rate_check_failed"}, "error": OK})

    def put(self, url, content=None, timeout=None, headers=None):
        self.calls.append(("PUT", url, headers))
        return FakeResponse({}, self.put_status)


def _connected():
    tiktok._save({"access_token": "act", "refresh_token": "r", "expires_at": time.time() + 3600,
                  "refresh_expires_at": time.time() + 86400})  # fmt: skip


def test_send_to_inbox_uploads_the_whole_file_and_waits_for_delivery(keys, tmp_path, monkeypatch):
    _connected()
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x" * 1234)
    fake = FakeClient(["PROCESSING_UPLOAD", "SEND_TO_USER_INBOX"])
    monkeypatch.setattr(httpx, "Client", lambda **kw: fake)
    monkeypatch.setattr(tiktok.time, "sleep", lambda s: None)

    assert tiktok.send_to_inbox(clip) == "v_inbox_file~1"
    init = fake.calls[0][2]["source_info"]
    assert init == {"source": "FILE_UPLOAD", "video_size": 1234, "chunk_size": 1234, "total_chunk_count": 1}
    put = fake.calls[1]
    assert put[1] == "https://up.tiktok/x?sig=1" and put[2]["Content-Range"] == "bytes 0-1233/1234"
    assert fake.calls[-1][2] == {"publish_id": "v_inbox_file~1"}


def test_send_to_inbox_reports_tiktoks_failure_reason(keys, tmp_path, monkeypatch):
    _connected()
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x" * 10)
    monkeypatch.setattr(httpx, "Client", lambda **kw: FakeClient(["FAILED"]))
    with pytest.raises(RuntimeError, match="frame_rate_check_failed"):
        tiktok.send_to_inbox(clip)


def test_publisher_marks_tiktok_as_sent_then_manual_mark_posts_it(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine, select

    from app import db
    from app.db import Clip, Job, Publish
    from app.main import app
    from app.publish import publisher

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "_engine", eng)
    monkeypatch.setattr(publisher, "get_engine", lambda: eng)
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    (tmp_path / "renders").mkdir()
    (tmp_path / "renders" / "a.mp4").write_bytes(b"x")
    monkeypatch.setattr(tiktok, "send_to_inbox", lambda path, progress=None: "v_inbox_file~9")
    with Session(eng) as s:
        job = Job(source_url="https://youtu.be/x")
        s.add(job)
        s.commit()
        clip = Clip(job_id=job.id, start=0, end=30, file_path="a.mp4")
        s.add(clip)
        s.commit()
        pub = Publish(clip_id=clip.id, platform="tiktok")
        s.add(pub)
        s.commit()
        pub_id, clip_id = pub.id, clip.id

    publisher.run(pub_id)
    with Session(eng) as s:
        assert s.get(Publish, pub_id).status == "sent"

    api = TestClient(app)
    r = api.post(f"/api/clips/{clip_id}/posted", json={"platform": "tiktok", "url": "https://www.tiktok.com/@me/video/1"})
    assert r.status_code == 200
    with Session(eng) as s:
        assert [p.status for p in s.exec(select(Publish).order_by(Publish.id))] == ["sent", "done"]
    assert api.delete(f"/api/clips/{clip_id}/posted/tiktok").json()["removed"] == 2
