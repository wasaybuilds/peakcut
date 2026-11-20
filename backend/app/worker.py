"""Background job runner. One job at a time (the laptop has one encoder and free APIs have rate limits).

Every pipeline step caches its output under data/cache/<video_id>/, so a crashed or
restarted job resumes from the step that failed.
"""

import logging
import queue
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.db import Clip, Job, JobStatus, get_engine
from app.pipeline import captions, cover, dash, facecam, highlights, ingest, metadata, render, signals, transcribe

log = logging.getLogger(__name__)

# step name -> (progress start, progress end)
STEPS = {
    "Fetching video info": (0.00, 0.03),
    "Downloading audio": (0.03, 0.15),
    "Transcribing": (0.15, 0.45),
    "Scanning for action": (0.45, 0.50),
    "Finding viral moments": (0.50, 0.65),
    "Rendering clips": (0.65, 1.00),
}

_queue: "queue.Queue[int]" = queue.Queue()
_started = False


def _update(job_id: int, **fields) -> None:
    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = datetime.now(UTC)
        s.add(job)
        s.commit()


def _stepper(job_id: int, name: str):
    a, b = STEPS[name]
    _update(job_id, step=name, progress=a)
    return lambda frac: _update(job_id, progress=round(a + (b - a) * min(1.0, max(0.0, frac)), 3))


def _render_cover(video: Path, clip: Clip, duration: float) -> dict | None:
    """Cover image next to the clip; keeps the user's chosen frame/text across re-renders."""
    prev = (clip.meta or {}).get("cover") or {}
    at = min(float(prev.get("at", cover.default_at(duration))), max(0.0, duration - 0.2))
    text = prev.get("text", clip.hook_text or clip.title)
    try:
        out = cover.make_cover(video, video.with_name(f"{video.stem}_cover.jpg"), at, text)
    except RuntimeError as e:
        log.warning("cover for clip %s failed: %s", clip.id, e)
        return prev or None
    return {"path": out.relative_to(get_settings().renders_dir).as_posix(), "at": at, "text": text}


def _find_facecam(job_id: int, vid: str, spans, source_for, src_aspect: float, out_dir: Path) -> dict:
    """Sample 2 frames from each clip (up to 8 clips) and look for a fixed face cam."""
    frames_dir = get_settings().cache_dir / vid / "frames"
    frames: list[Path] = []
    for n, (start, end) in enumerate(spans[:8]):
        src = source_for(start, end)
        for k, t in enumerate((start + 2, (start + end) / 2)):
            if isinstance(src, Path):
                path, at, headers = str(src), t, ""
            else:
                path, at, headers = src.video, t - src.video_start, src.headers
            f = facecam.grab_frame(path, at, frames_dir / f"f{n}_{k}.jpg", headers)
            if f:
                frames.append(f)
    box = facecam.detect(frames, src_aspect)
    result: dict = {"facecam": box}
    if frames:  # keep a frame so the user can see/adjust the box in the web app
        preview = out_dir / f"job{job_id}_frame.jpg"
        out_dir.mkdir(parents=True, exist_ok=True)
        preview.write_bytes(frames[len(frames) // 2].read_bytes())
        result["facecam_frame"] = preview.relative_to(get_settings().renders_dir).as_posix()
    log.info("face cam for job %s: %s", job_id, box)
    return result


def run_job(job_id: int) -> None:
    settings = get_settings()
    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        if not job:
            return
        url, opts = job.source_url, dict(job.options or {})
    count = int(opts.get("clip_count") or settings.default_clip_count)
    layout = opts.get("layout") or "zoom_fill"
    style = opts.get("caption_style") or "bold_pop"

    _update(job_id, status=JobStatus.running, error=None)
    try:
        p = _stepper(job_id, "Fetching video info")
        vid = ingest.video_id_for(url)
        # metadata never goes stale, only stream URLs do (refreshed again before rendering)
        info = ingest.cached_info(vid) or ingest.fetch_info(url, vid)
        if info.get("is_live"):
            raise RuntimeError("This stream is still live. Try again after it ends and the VOD is up.")
        duration = float(info.get("duration") or 0)
        _update(job_id, video_id=vid, title=info.get("title"), channel=info.get("channel"), duration=duration)
        # Long streams: only analyze the most-replayed stretch (or the range the user chose).
        if opts.get("start") is not None or opts.get("end") is not None:
            lo = max(0.0, float(opts.get("start") or 0))
            hi = min(duration, float(opts.get("end") or duration))
        else:
            lo, hi = signals.best_window(info, duration, settings.max_analyze_seconds)
        whole = lo <= 0 and hi >= duration
        workdir = ingest.job_dir(vid) if whole else ingest.job_dir(vid) / f"range_{int(lo)}_{int(hi)}"
        _update(job_id, options={**opts, "analyzed": [lo, hi]})
        p(1)

        seg = ingest.segmented_formats(info)
        audio_progress = _stepper(job_id, "Downloading audio")
        offset = lo
        cached_steps = (workdir / "transcript.json").exists() and (workdir / "signals.json").exists()
        if cached_steps:
            audio = workdir / "audio.m4a"  # unused: transcript + signals load from cache
        elif seg and not whole:
            # long stream VOD: fetch just the pieces we need, straight from YouTube
            if time.time() - info.get("_fetched_at", 0) > ingest.INFO_MAX_AGE:
                info = ingest.fetch_info(url, vid, force=True)  # piece URLs expire
                seg = ingest.segmented_formats(info)
            workdir.mkdir(parents=True, exist_ok=True)
            audio = workdir / "audio.m4a"
            offset = dash.download_range(seg[1], lo, hi, audio, progress=audio_progress)
        else:
            audio = ingest.download_audio(
                url, vid, workdir, None if whole else (lo, hi), total=duration, progress=audio_progress
            )
        transcript = transcribe.transcribe(
            audio, hi - lo + 4, workdir, offset=offset, progress=_stepper(job_id, "Transcribing")
        )

        p = _stepper(job_id, "Scanning for action")
        sig = signals.compute(audio, info, workdir, offset=offset)
        p(1)

        picks = highlights.find(
            info, transcript, sig, workdir, count, span=(lo, hi), progress=_stepper(job_id, "Finding viral moments")
        )
        if not picks:
            raise RuntimeError("No highlights found in this video.")

        # (re)create clip rows for this job
        with Session(get_engine()) as s:
            existing = s.exec(select(Clip).where(Clip.job_id == job_id)).all()
            if len(existing) != len(picks):
                for c in existing:
                    s.delete(c)
                s.commit()
                _update(job_id, step="Writing captions")
                metas = metadata.generate(
                    [{"title": h.title, "hook_text": h.hook, "reason": h.reason, "start": h.start, "end": h.end,
                      "meta": {"hashtags": h.hashtags}} for h in picks], info, transcript["words"],
                )  # fmt: skip
                for h, m in zip(picks, metas, strict=True):
                    s.add(Clip(job_id=job_id, start=h.start, end=h.end, score=h.score, title=h.title,
                               hook_text=h.hook, reason=h.reason, layout=layout, caption_style=style,
                               meta=m))  # fmt: skip
                s.commit()
            clip_ids = [c.id for c in s.exec(select(Clip).where(Clip.job_id == job_id).order_by(Clip.id)).all()]

        p = _stepper(job_id, "Rendering clips")
        segmented = ingest.segmented_formats(info) is not None
        src_aspect = (info.get("width") or 16) / (info.get("height") or 9)
        credit = f"via {info.get('uploader_id') or info.get('channel') or ''}".strip()
        out_dir = settings.renders_dir / vid
        # Stream URLs expire; refresh info only once something actually has to be fetched.
        state: dict = {"info": None, "src": None, "remote_tried": False}

        def fresh_info() -> dict:
            if state["info"] is None:
                state["info"] = ingest.fetch_info(url, vid)
            return state["info"]

        def source_for(start: float, end: float):
            if segmented:
                cached = ingest.cached_section(vid, start, end)
                return cached or ingest.segmented_section(fresh_info(), vid, start, end)
            if state["src"] is None and not state["remote_tried"]:
                state["remote_tried"] = True
                state["src"] = ingest.stream_source(fresh_info())
            if state["src"] is None:
                state["src"] = ingest.download_full_video(url, vid)
            return state["src"]

        with Session(get_engine()) as s:
            clips_now = [s.get(Clip, cid) for cid in clip_ids]
            needs_cam = any(c.layout == "facecam_split" for c in clips_now)
            spans = [(c.start, c.end) for c in clips_now]
            opts = dict(s.get(Job, job_id).options or {})
        if needs_cam and "facecam" not in opts:
            _update(job_id, step="Finding the face cam")
            opts.update(_find_facecam(job_id, vid, spans, source_for, src_aspect, out_dir))
            _update(job_id, options=opts, step="Rendering clips")
        cam = opts.get("facecam")
        hook_y = render.facecam_height(cam, src_aspect) - 60 if cam else 300

        for i, cid in enumerate(clip_ids):
            with Session(get_engine()) as s:
                clip = s.get(Clip, cid)
                if clip.file_path and (settings.renders_dir / clip.file_path).exists():
                    p((i + 1) / len(clip_ids))
                    continue
                start, end, hook, c_style, c_layout = clip.start, clip.end, clip.hook_text, clip.caption_style, clip.layout
            split = c_layout == "facecam_split" and cam
            ass = captions.build_ass(transcript["words"], start, end, style=c_style, hook=hook, credit=credit,
                                     hook_y=hook_y if split else 300)  # fmt: skip
            # unique name per render so browsers never show a cached old version
            out = out_dir / f"job{job_id}_clip{i + 1:02d}_{int(time.time()) % 1_000_000}.mp4"
            kw = {"layout": c_layout, "facecam": cam, "src_aspect": src_aspect}
            clip_src = source_for(start, end)
            try:
                render.render_clip(clip_src, start, end, ass, out, **kw)
            except render.RenderError as e:
                if segmented or isinstance(clip_src, Path):
                    raise
                log.warning("remote render failed (%s); downloading the video instead", str(e)[-200:])
                state["src"] = ingest.download_full_video(url, vid)
                render.render_clip(state["src"], start, end, ass, out, **kw)
            except Exception:
                if not segmented:
                    raise
                # expired piece URLs: refresh once and fetch this section again
                state["info"] = ingest.fetch_info(url, vid, force=True)
                clip_src = ingest.segmented_section(state["info"], vid, start, end)
                render.render_clip(clip_src, start, end, ass, out, **kw)
            thumb = render.thumbnail(out)
            with Session(get_engine()) as s:
                clip = s.get(Clip, cid)
                clip.file_path = out.relative_to(settings.renders_dir).as_posix()
                clip.thumb_path = thumb.relative_to(settings.renders_dir).as_posix() if thumb.exists() else None
                clip.meta = {**(clip.meta or {}), "cover": _render_cover(out, clip, end - start)}
                s.add(clip)
                s.commit()
            p((i + 1) / len(clip_ids))

        _update(job_id, status=JobStatus.done, step="Done", progress=1.0)
    except Exception as e:
        log.error("job %s failed: %s", job_id, traceback.format_exc())
        _update(job_id, status=JobStatus.failed, error=str(e)[:2000])


def _loop() -> None:
    while True:
        job_id = _queue.get()
        try:
            run_job(job_id)
        finally:
            _queue.task_done()


def enqueue(job_id: int) -> None:
    _queue.put(job_id)


def start() -> None:
    """Start the worker thread and re-queue unfinished jobs (resume after restart)."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, name="clip-worker", daemon=True).start()
    with Session(get_engine()) as s:
        for job in s.exec(select(Job).where(Job.status.in_([JobStatus.queued, JobStatus.running]))):
            enqueue(job.id)
