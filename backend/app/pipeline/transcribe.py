"""Speech-to-text with word timestamps: Groq Whisper -> local faster-whisper.

Output (transcript.json): {"words": [{"w","s","e"}], "segments": [{"s","e","text"}], "engine"}
"""

import json
import logging
import math
import subprocess
from pathlib import Path

from app.config import get_settings
from app.ffmpeg import ffmpeg_bin, media_duration

log = logging.getLogger(__name__)

CHUNK_SECONDS = 20 * 60  # 20 min of 48 kbps mono mp3 ~ 7 MB, well under Groq's 25 MB cap


def _extract_chunk(audio: Path, out: Path, start: float, length: float) -> None:
    cmd = [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-max_error_rate", "1",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(audio),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(out),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)


def _groq_chunk(path: Path, offset: float) -> dict:
    from groq import Groq

    client = Groq(api_key=get_settings().groq_api_key, max_retries=3, timeout=300)
    with open(path, "rb") as f:
        r = client.audio.transcriptions.create(
            file=(path.name, f.read()),
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    data = r.model_dump() if hasattr(r, "model_dump") else dict(r)
    words = [
        {"w": w["word"].strip(), "s": round(w["start"] + offset, 2), "e": round(w["end"] + offset, 2)}
        for w in data.get("words") or []
        if w.get("word", "").strip()
    ]
    segments = [
        {"s": round(s["start"] + offset, 2), "e": round(s["end"] + offset, 2), "text": s["text"].strip()}
        for s in data.get("segments") or []
        if s.get("text", "").strip() and s.get("no_speech_prob", 0) < 0.8
    ]
    return {"words": words, "segments": segments}


_local_model = None


def _local_chunk(path: Path, offset: float) -> dict:
    """CPU fallback. int8 'small' runs several x realtime on a modern laptop CPU."""
    global _local_model
    from faster_whisper import WhisperModel

    if _local_model is None:
        _local_model = WhisperModel(get_settings().local_whisper_model, device="cpu", compute_type="int8")
    segs, _ = _local_model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    words, segments = [], []
    for s in segs:
        segments.append({"s": round(s.start + offset, 2), "e": round(s.end + offset, 2), "text": s.text.strip()})
        for w in s.words or []:
            if w.word.strip():
                words.append({"w": w.word.strip(), "s": round(w.start + offset, 2), "e": round(w.end + offset, 2)})
    return {"words": words, "segments": segments}


def transcribe(audio: Path, duration: float, workdir: Path, offset: float = 0.0, progress=None) -> dict:
    """`duration` = length of the audio file; `offset` = where it starts in the source video."""
    out_path = workdir / "transcript.json"
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    chunk_dir = workdir / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    real = media_duration(audio)  # trust the file over the expected length
    if real:
        duration = real
    n = max(1, math.ceil(duration / CHUNK_SECONDS))
    use_groq = bool(get_settings().groq_api_key)
    result = {"words": [], "segments": [], "engine": "groq" if use_groq else "local"}

    for i in range(n):
        cached = chunk_dir / f"{i:03d}.json"
        if cached.exists():
            part = json.loads(cached.read_text(encoding="utf-8"))
        else:
            start = i * CHUNK_SECONDS
            mp3 = chunk_dir / f"{i:03d}.mp3"
            _extract_chunk(audio, mp3, start, CHUNK_SECONDS)
            part = None
            if use_groq:
                try:
                    part = _groq_chunk(mp3, offset + start)
                except Exception as e:  # rate limit / outage -> local model for this chunk
                    log.warning("Groq transcription failed on chunk %d: %s; using local model", i, e)
                    result["engine"] = "mixed"
            if part is None:
                part = _local_chunk(mp3, offset + start)
            cached.write_text(json.dumps(part), encoding="utf-8")
            mp3.unlink(missing_ok=True)
        result["words"] += part["words"]
        result["segments"] += part["segments"]
        if progress:
            progress((i + 1) / n)

    out_path.write_text(json.dumps(result), encoding="utf-8")
    return result
