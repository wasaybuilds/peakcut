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
