"""Run the pipeline without the web app:  uv run python -m app.cli <youtube-url> [--count 5]"""

import argparse
import logging
import threading
import time

from sqlmodel import Session, select

from app.config import get_settings
from app.db import Clip, Job, get_engine, init_db
from app.worker import run_job


def main() -> None:
    ap = argparse.ArgumentParser(description="clip-kr: YouTube link -> viral 9:16 clips")
    ap.add_argument("url")
    ap.add_argument("--count", type=int, default=get_settings().default_clip_count)
    ap.add_argument("--layout", default="zoom_fill", choices=["zoom_fill", "blur_fill", "center_crop"])
    ap.add_argument("--style", default="bold_pop", choices=["bold_pop", "beast", "minimal"])
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    get_settings().ensure_dirs()
    init_db()
    with Session(get_engine()) as s:
        job = Job(source_url=args.url, options={"clip_count": args.count, "layout": args.layout,
                                                "caption_style": args.style})  # fmt: skip
        s.add(job)
        s.commit()
        job_id = job.id

    t = threading.Thread(target=run_job, args=(job_id,))
    t.start()
    last = None
    while t.is_alive():
        with Session(get_engine()) as s:
            j = s.get(Job, job_id)
            line = f"[{j.progress * 100:5.1f}%] {j.step or 'starting'}"
        if line != last:
            print(line, flush=True)
            last = line
        time.sleep(1)

    with Session(get_engine()) as s:
        j = s.get(Job, job_id)
        if j.status != "done":
            print(f"FAILED: {j.error}")
            raise SystemExit(1)
        for c in s.exec(select(Clip).where(Clip.job_id == job_id).order_by(Clip.score.desc())):
            print(f"{c.score:3d}  {c.start:8.1f}-{c.end:<8.1f} {c.title}\n     -> {get_settings().renders_dir / c.file_path}")


if __name__ == "__main__":
    main()
