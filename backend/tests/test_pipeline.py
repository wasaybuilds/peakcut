import numpy as np

from app.pipeline.captions import build_ass, group_words
from app.pipeline.highlights import Highlight, dedupe, snap
from app.pipeline.signals import hot_spots, relative_loudness

SEGMENTS = [
    {"s": 10.0, "e": 14.0, "text": "Yo look at this car"},
    {"s": 14.5, "e": 20.0, "text": "No way he just did that"},
    {"s": 40.0, "e": 44.0, "text": "That was insane"},
]


def test_snap_moves_to_sentence_boundaries():
    h = Highlight(start=11.2, end=42.5, score=80, title="t", hook="h", reason="r")
    out = snap(h, SEGMENTS, duration=100, min_len=15, max_len=60)
    assert out.start == 9.85  # segment start 10.0 minus lead-in
    assert out.end == 44.3  # segment end 44.0 plus tail


def test_snap_enforces_min_and_max_length():
    short = snap(Highlight(50, 52, 50, "", "", ""), [], duration=100, min_len=15, max_len=60)
    assert 14.9 <= short.end - short.start <= 15.6
    long = snap(Highlight(0, 90, 50, "", "", ""), [], duration=100, min_len=15, max_len=60)
    assert long.end - long.start == 60


def test_dedupe_keeps_higher_score_on_overlap():
    a = Highlight(0, 30, 90, "a", "", "")
    b = Highlight(5, 35, 70, "b", "", "")  # heavy overlap with a
    c = Highlight(60, 80, 60, "c", "", "")
    assert [h.title for h in dedupe([b, a, c])] == ["a", "c"]


def test_group_words_breaks_on_count_and_punctuation():
    words = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate(["no", "way.", "he", "did", "that", "again", "bro"])]
    groups = [[w["w"] for w in g] for g in group_words(words)]
    assert groups[0] == ["no", "way."]
    assert all(len(g) <= 3 for g in groups)


def test_build_ass_shifts_times_and_highlights_words():
    words = [{"w": "hello", "s": 100.0, "e": 100.4}, {"w": "world", "s": 100.5, "e": 101.0}]
    ass = build_ass(words, 99.0, 120.0, hook="Watch this", credit="via @someone")
    assert "PlayResX: 1080" in ass
    assert "Dialogue: 1,0:00:01.00" in ass  # 100.0 - 99.0
    assert "HELLO" in ass and "WORLD" in ass
    assert "WATCH THIS" in ass and "via @someone" in ass
    assert ass.count("Style: Cap") == 1


def test_hot_spots_finds_loud_peak():
    rel = np.zeros(300)
    rel[150:153] = 15  # explosion
    spots = hot_spots({"loudness_rel": rel.tolist(), "heatmap": [0] * 300}, 0, 300)
    assert spots and abs(spots[0]["t"] - 151) <= 1


def test_best_window_picks_most_replayed_stretch():
    from app.pipeline.signals import best_window

    info = {"heatmap": [{"start_time": 0, "end_time": 5000, "value": 0.1},
                        {"start_time": 5000, "end_time": 6000, "value": 1.0},
                        {"start_time": 6000, "end_time": 20000, "value": 0.1}]}  # fmt: skip
    a, b = best_window(info, 20000, 2000)
    assert b - a == 2000 and a <= 5000 and b >= 6000
    assert best_window({}, 20000, 2000) == (0.0, 2000.0)
    assert best_window(info, 1500, 2000) == (0.0, 1500)


def test_facecam_split_chain_stacks_cam_over_gameplay():
    from app.pipeline.render import _video_chain, facecam_height

    box = {"x": 0.0, "y": 0.6, "w": 0.25, "h": 0.33}  # bottom-left webcam
    top = facecam_height(box)
    assert 480 <= top <= 900 and top % 2 == 0
    chain = _video_chain("facecam_split", "c.ass", "nv12", box)
    assert "vstack=inputs=2" in chain and f"crop=1080:{1920 - top}" in chain
    # no box detected -> falls back to the zoom layout instead of failing
    assert "overlay" in _video_chain("facecam_split", "c.ass", "nv12", None)


def test_facecam_detect_needs_a_face_in_the_same_spot(tmp_path, monkeypatch):
    from app.pipeline import facecam

    frames = []
    for i in range(6):
        f = tmp_path / f"{i}.jpg"
        f.write_bytes(b"x")
        frames.append(f)
    moving = iter([[(0.1 + i * 0.15, 0.5, 0.05, 0.09)] for i in range(6)])  # game face moving around
    fixed = [(0.9, 0.85, 0.05, 0.09)]  # webcam face, same place every frame
    monkeypatch.setattr("cv2.imread", lambda p: object())
    monkeypatch.setattr(facecam, "_faces", lambda img: next(moving) + fixed)
    box = facecam.detect(frames)
    assert box and box["x"] > 0.7 and box["y"] > 0.6
    assert box["x"] + box["w"] <= 1 and box["y"] + box["h"] <= 1


def test_cover_text_sits_in_the_profile_grid_band():
    from app.pipeline.cover import GRID_BOTTOM, GRID_TOP, cover_ass, default_at

    ass = cover_ass("Stole it {from} my mother")
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert f"\\pos(540,{(GRID_TOP + GRID_BOTTOM) // 2})" in ass  # centre of the 3:4 grid crop
    assert "STOLE IT (FROM) MY MOTHER" in ass  # uppercased, override braces neutralised
    assert 0 < default_at(30) < 30 and default_at(0.1) == 0.0


def test_relative_loudness_is_zero_for_flat_audio():
    assert np.allclose(relative_loudness(np.full(500, -20.0)), 0)
