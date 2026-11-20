from app.pipeline import metadata


def test_generate_uses_llm_text_and_builds_platform_fields(monkeypatch):
    def fake_chat(system, user):
        assert "IShowSpeed" in user and "transcript" in user
        return {"clips": [{"n": 1, "yt_title": "Speed found out he has a SON", "ig_caption": "Wait for it 😭\nWould you?",
                           "hashtags": ["gta6funny", "#ishowspeed", "#GTA6"]}]}, "zhipu"  # fmt: skip

    monkeypatch.setattr(metadata, "chat_json", fake_chat)
    info = {"channel": "IShowSpeed", "title": "GTA 6 stream", "webpage_url": "https://youtu.be/x"}
    words = [{"w": "we", "s": 10.0, "e": 10.2}, {"w": "got", "s": 10.3, "e": 10.5}]
    [m] = metadata.generate([{"title": "t", "hook_text": "h", "reason": "r", "start": 9, "end": 20, "meta": {}}],
                            info, words)  # fmt: skip

    assert m["youtube"]["title"] == "Speed found out he has a SON #shorts"
    assert "IShowSpeed" in m["youtube"]["description"] and "https://youtu.be/x" in m["youtube"]["description"]
    assert m["youtube"]["privacy"] == "public"
    assert m["instagram"]["caption"].startswith("Wait for it 😭")
    tags_lower = [t.lower() for t in m["hashtags"]]
    assert "#gta6funny" in tags_lower and tags_lower.count("#gta6") == 1  # normalized + de-duplicated
    assert "gta6funny" in m["youtube"]["tags"]  # YouTube tags have no '#'


def test_generate_falls_back_when_llm_fails(monkeypatch):
    def boom(system, user):
        raise RuntimeError("all providers down")

    monkeypatch.setattr(metadata, "chat_json", boom)
    [m] = metadata.generate([{"title": "Cops chase", "hook_text": "", "reason": "", "start": 0, "end": 5,
                              "meta": {"youtube": {"privacy": "unlisted"}}}], {"channel": "X"}, [])  # fmt: skip
    assert m["youtube"]["title"].startswith("Cops chase")
    assert m["youtube"]["privacy"] == "unlisted"  # keeps the user's earlier choice
    assert "#gta6" in m["hashtags"]
