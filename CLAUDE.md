# PeakCut

YouTube link in, captioned 9:16 clips out, posted to YouTube Shorts and Instagram Reels. Everything runs locally on a laptop without an NVIDIA GPU and uses only free AI tiers. Product truth lives in [PRODUCT.md](PRODUCT.md); the visual system lives in [DESIGN.md](DESIGN.md).

## Layout

```
backend/   FastAPI + clipping pipeline (Python 3.13, uv)
  app/main.py         app, routers, static /files, starts both worker threads
  app/worker.py       job runner: one job at a time, every step cached under data/cache/<video_id>/
  app/pipeline/       ingest (yt-dlp) -> dash (stream VOD pieces) -> transcribe -> signals -> highlights
                      -> metadata (AI captions) -> facecam -> captions (ASS) -> render (ffmpeg)
  app/llm/            free provider chain (Z.ai, SiliconFlow, Groq, OpenRouter, Gemini) with fallback
  app/publish/        youtube.py, instagram.py, publisher.py (separate upload thread)
  app/api/            jobs.py, publish.py
frontend/  Next.js 15 app router + Tailwind v4
  app/globals.css     design tokens and component classes (the only place colours are defined)
  components/         shell, marquee primitives (LetterTitle, BulbChase, StateMarks), layout panel, post dialog
data/      gitignored: downloads, cache, renders, peakcut.db (SQLite)
backend/tokens/       gitignored: OAuth client, YouTube/Instagram tokens, youtube_cookies.txt
```

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # one-time install
powershell -File scripts\dev.ps1                             # API :8000 + web :3000

cd backend
uv run python -m pytest -q                 # tests
uv run python -m ruff check app tests      # lint
uv run python -m uvicorn app.main:app --port 8000
uv run python -m app.cli <youtube-url> --count 3   # pipeline without the web app

cd frontend
npx tsc --noEmit; npx eslint app lib components
npm run build   # only with the dev server stopped: both use .next, and a build breaks a running dev server (500s)
```

## Windows Smart App Control (read before adding Python deps)

The dev machine enforces Smart App Control, which blocks:

- uv-managed Pythons and uv's `.exe` launchers. The venv is built on the signed python.org 3.13 and tools always run as `python -m <tool>`, never `pytest` / `uvicorn` directly.
- native wheels from very new releases. `backend/pyproject.toml` pins known-good versions in `[tool.uv] constraint-dependencies` (pydantic-core, jiter, sqlalchemy, opencv-python-headless). After adding a dependency, test-import it; if it is blocked, pin an older release.

## Pipeline rules

- Every step writes its output to the cache and reads it back on rerun. Keep it that way: jobs resume after crashes, and re-renders skip straight to rendering.
- Long videos: only `MAX_ANALYZE_SECONDS` (2 h) of the most-replayed stretch is analyzed. Stream VODs served as DASH pieces are fetched piece by piece in `pipeline/dash.py`; piece length is measured, never derived from duration/count.
- Clip times are absolute seconds in the source video everywhere (transcript words, highlights, sections). Renders subtract each input's own start offset.
- YouTube's bot check is solved with `backend/tokens/youtube_cookies.txt`; surface `YouTubeBlocked` messages to the user verbatim.
- Uploads never retry blindly after a crash: an interrupted upload is marked failed for the user to check.

## Design rules (frontend)

- Marquee Letterboard: felt black shell, letter-white ink, Big Shoulders (one family, optical sizes).
- Colour does one job each: amber `--bulb` = live progress, red `--fail` = failure, green `--posted` = posted. Nothing else gets colour.
- Radius: 4px (`--radius`) for every UI surface, 2px for physical plates (letter tiles, score plate), full circles only for bulbs, marks and the play button. One-pixel rules. Component classes (`.btn`, `.field`, `.tile`) live in `@layer components` so utilities can override them.
- Never hard-code a colour: add a token in `globals.css` first. The full token set and named rules are in [DESIGN.md](DESIGN.md) and `.impeccable/design.json`.
- No eyebrow labels above headings, no em-dashes in any visible text, icons from lucide only, every state (loading, empty, error, disabled) designed.

## Repo hygiene

- Never commit `.env`, `backend/tokens/`, or `data/`. The repo is public.
- Commits: conventional style (`feat(scope): ...`, `fix(scope): ...`), one logical change each.
