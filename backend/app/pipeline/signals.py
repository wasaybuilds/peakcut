"""Per-second "something is happening" signals that don't need speech.

- loudness: gunfire, crashes, streamer yelling (relative to the local baseline)
- heatmap: YouTube "most replayed" curve from info.json
Chat replay spikes come in M3.
"""

import json
import subprocess
from pathlib import Path

import numpy as np

from app.ffmpeg import ffmpeg_bin

SAMPLE_RATE = 4000


def loudness_per_second(audio: Path) -> np.ndarray:
    """RMS loudness in dB for each second of audio."""
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-max_error_rate", "1", "-i", str(audio),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-",
    ]  # fmt: skip
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    n = len(pcm) // SAMPLE_RATE
    if n == 0:
        return np.zeros(0)
    frames = pcm[: n * SAMPLE_RATE].reshape(n, SAMPLE_RATE)
    rms = np.sqrt(np.mean(frames**2, axis=1)) + 1e-6
    return 20 * np.log10(rms)


def relative_loudness(db: np.ndarray, window: int = 120) -> np.ndarray:
    """dB above the rolling median of the surrounding `window` seconds."""
    if len(db) == 0:
        return db
    pad = window // 2
    padded = np.pad(db, pad, mode="edge")
    # rolling median via strided view (fine for multi-hour audio at 1 value/sec)
    view = np.lib.stride_tricks.sliding_window_view(padded, window + 1)
    base = np.median(view, axis=1)[: len(db)]
    return db - base


def heatmap_per_second(info: dict, n: int) -> np.ndarray:
    out = np.zeros(n)
    for p in info.get("heatmap") or []:
        a, b = int(p["start_time"]), int(np.ceil(p["end_time"]))
        out[a : min(b, n)] = p["value"]
    return out


def best_window(info: dict, duration: float, length: float) -> tuple[float, float]:
    """The `length`-second stretch with the most replay heat (start of video if no heatmap)."""
    if duration <= length:
        return 0.0, duration
    n, L = int(duration), int(length)
    heat = heatmap_per_second(info, n)
    if not heat.any():
        return 0.0, float(length)
    csum = np.concatenate([[0.0], np.cumsum(heat)])
    a = int(np.argmax(csum[L:] - csum[:-L]))
    return float(a), float(a + L)


def compute(audio: Path, info: dict, workdir: Path, offset: float = 0.0) -> dict:
    """Per-second arrays over the whole video; loudness is filled in where `audio` covers it."""
    path = workdir / "signals.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    part = relative_loudness(loudness_per_second(audio))
    total = max(int(info.get("duration") or 0), int(offset) + len(part))
    rel = np.zeros(total)
    rel[int(offset) : int(offset) + len(part)] = part
    heat = heatmap_per_second(info, total)
    data = {"loudness_rel": np.round(rel, 2).tolist(), "heatmap": np.round(heat, 3).tolist()}
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def hot_spots(signals: dict, start: float, end: float, top: int = 12, min_gap: int = 20) -> list[dict]:
    """Strongest moments in [start, end): combined score of loudness spike + replay heat."""
    rel = np.array(signals["loudness_rel"])
    heat = np.array(signals["heatmap"])
    if len(rel) == 0:
        return []
    a, b = max(0, int(start)), min(len(rel), int(end))
    if b <= a:
        return []
    # smooth over 3s so a single gunshot doesn't dominate
    k = np.ones(3) / 3
    loud = np.convolve(rel, k, mode="same")
    score = np.clip(loud, 0, None) / 10 + heat * 1.5
    order = np.argsort(score[a:b])[::-1] + a
    picked: list[int] = []
    for t in order:
        if score[t] <= 0.15:
            break
        if all(abs(t - p) >= min_gap for p in picked):
            picked.append(int(t))
        if len(picked) >= top:
            break
    return [
        {"t": t, "loud_db": round(float(loud[t]), 1), "heat": round(float(heat[t]), 2),
         "score": round(float(score[t]), 2)}
        for t in sorted(picked)
    ]  # fmt: skip
