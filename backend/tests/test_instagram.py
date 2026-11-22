import httpx
import pytest

from app.publish import instagram


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._data


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(instagram, "TOKEN", tmp_path / "instagram.json")
    return tmp_path / "instagram.json"


def test_unified_login_token_finds_account_from_its_grants(saved, monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.endswith("/debug_token"):
            return FakeResponse({"data": {"granular_scopes": [
                {"scope": "instagram_content_publish", "target_ids": ["1784"]},
            ]}})  # fmt: skip
        if url.endswith("/1784"):
            return FakeResponse({"id": "1784", "username": "mostreplayed"})
        return FakeResponse({"error": {"message": "unexpected"}}, 400)

    monkeypatch.setattr(httpx, "get", fake_get)
    data = instagram.connect("EAAtesttoken" + "x" * 20)
    assert data["api"] == "facebook" and data["user_id"] == "1784" and data["username"] == "mostreplayed"
    assert all(u.startswith(instagram.FB_GRAPH) for u in calls)
    assert instagram._graph(data) == instagram.FB_GRAPH


def test_unified_login_token_uses_pasted_account_id(saved, monkeypatch):
    seen = []

    def fake_get(url, params=None, timeout=None):
        seen.append(url)
        return FakeResponse({"id": "42", "username": "mostreplayed"})

    monkeypatch.setattr(httpx, "get", fake_get)
    assert instagram.connect("EAA" + "x" * 30, " 42 ")["user_id"] == "42"
    assert seen == [f"{instagram.FB_GRAPH}/{instagram._version()}/42"]  # no lookup needed


def test_unified_login_token_without_account_asks_for_the_id(saved, monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params=None, timeout=None: FakeResponse({"data": []}))
    with pytest.raises(RuntimeError, match="account ID"):
        instagram.connect("EAA" + "x" * 30)
    assert not saved.exists()


def test_instagram_login_token_keeps_using_graph_instagram(saved, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert url.startswith(instagram.IG_GRAPH)
        return FakeResponse({"user_id": 7, "username": "mostreplayed", "account_type": "MEDIA_CREATOR"})

    monkeypatch.setattr(httpx, "get", fake_get)
    data = instagram.connect("IGAA" + "x" * 30)
    assert data["api"] == "instagram" and data["user_id"] == "7"
    assert instagram._graph(data) == instagram.IG_GRAPH


class FakeRupload:
    """rupload: 206 + stored offset for partial pieces, 200 once the whole file is in."""

    def __init__(self, size, stall=False):
        self.size, self.held, self.stall, self.posts = size, 0, stall, []

    def post(self, url, content=None, timeout=None, headers=None):
        self.posts.append((int(headers["offset"]), len(content)))
        assert int(headers["offset"]) == self.held and headers["file_size"] == str(self.size)
        if not self.stall:
            self.held += len(content)
        if self.held >= self.size:
            return FakeResponse({"success": True})
        return FakeResponse({"debug_info": {"type": "PartialRequestError"}}, 206)

    def get(self, url, headers=None):
        return FakeResponse({"offset": self.held})


def test_upload_sends_the_file_in_pieces_until_rupload_has_it_all(tmp_path, monkeypatch):
    monkeypatch.setattr(instagram, "UPLOAD_CHUNK", 10)
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x" * 25)
    fake = FakeRupload(25)
    instagram._upload(fake, "https://rupload/x", clip, "tok", 25)
    assert fake.posts == [(0, 10), (10, 10), (20, 5)]

    small = FakeRupload(25)
    monkeypatch.setattr(instagram, "UPLOAD_CHUNK", 100)
    instagram._upload(small, "https://rupload/x", clip, "tok", 25)
    assert small.posts == [(0, 25)]  # small files still go in one request

    monkeypatch.setattr(instagram, "UPLOAD_CHUNK", 10)
    with pytest.raises(RuntimeError, match="stopped taking"):
        instagram._upload(FakeRupload(25, stall=True), "https://rupload/x", clip, "tok", 25)


class FakeGraph:
    """Graph API side of a Reel post: containers, status, publish, permalink."""

    def __init__(self, finishes=True):
        self.containers, self.published, self.finishes = 0, [], finishes

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, data=None, **kw):
        if url.endswith("/media"):
            self.containers += 1
            return FakeResponse({"id": f"c{self.containers}"})
        self.published.append(data["creation_id"])
        return FakeResponse({"id": "m1"})

    def get(self, url, params=None, **kw):
        if params and params.get("fields") == "permalink":
            return FakeResponse({"permalink": "https://www.instagram.com/reel/x/"})
        # the dropped container never finishes; the retried one does
        done = self.finishes and not url.endswith("/c1")
        return FakeResponse({"status_code": "FINISHED" if done else "IN_PROGRESS"})


def test_publish_starts_over_when_meta_drops_the_upload(saved, tmp_path, monkeypatch):
    instagram._save({"access_token": "EAAx", "user_id": "1784", "api": "facebook"})
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x" * 10)
    graph = FakeGraph()
    monkeypatch.setattr(httpx, "Client", lambda **kw: graph)
    uploads = []

    def flaky_upload(client, url, path, tok, size):
        uploads.append(url)
        if len(uploads) == 1:
            raise RuntimeError('Instagram: {"debug_info":{"type":"ProcessingFailedError"}}')

    monkeypatch.setattr(instagram, "_upload", flaky_upload)
    assert instagram.publish(clip, "caption") == "https://www.instagram.com/reel/x/"
    assert [u.rsplit("/", 1)[1] for u in uploads] == ["c1", "c2"] and graph.published == ["c2"]

    def always_fails(client, url, path, tok, size):
        raise RuntimeError('Instagram: {"debug_info":{"type":"ProcessingFailedError"}}')

    monkeypatch.setattr(instagram, "_upload", always_fails)
    monkeypatch.setattr(httpx, "Client", lambda **kw: FakeGraph(finishes=False))
    with pytest.raises(RuntimeError, match="dropped the upload 3 times"):
        instagram.publish(clip, "caption")
