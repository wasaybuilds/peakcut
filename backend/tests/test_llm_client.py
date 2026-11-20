from app.config import Settings
from app.llm import client
from app.llm.client import parse_json
from app.llm.providers import configured_chain


def test_parse_json_strips_fence_and_think():
    raw = '<think>hmm</think>\n```json\n{"clips": [{"start": 1}]}\n```'
    assert parse_json(raw) == {"clips": [{"start": 1}]}


def test_parse_json_extracts_embedded_object():
    assert parse_json('Sure! Here you go: {"a": 1} hope that helps') == {"a": 1}


def test_chain_skips_providers_without_keys():
    s = Settings(_env_file=None, zhipu_api_key="", groq_api_key="x", gemini_api_key="y",
                 llm_order="zhipu,groq,gemini")  # fmt: skip
    assert [p.name for p in configured_chain(s)] == ["groq", "gemini"]


def test_chat_json_falls_back_on_rate_limit(monkeypatch):
    s = Settings(_env_file=None, zhipu_api_key="a", groq_api_key="b", llm_order="zhipu,groq")
    calls = []

    def fake_call(spec, settings, system, user):
        calls.append(spec.name)
        if spec.name == "zhipu":
            raise RuntimeError("429 Too Many Requests")
        return '{"ok": true}'

    monkeypatch.setattr(client, "_call", fake_call)
    data, used = client.chat_json("sys", "user", settings=s)
    assert data == {"ok": True}
    assert used == "groq"
    assert calls == ["zhipu", "groq"]
