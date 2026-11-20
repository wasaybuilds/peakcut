"""FastAPI entrypoint: `uv run uvicorn app.main:app --reload`"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import ffmpeg, worker
from app.api.jobs import router as jobs_router
from app.api.publish import router as publish_router
from app.config import get_settings
from app.db import init_db
from app.llm.client import LLMError, chat_json
from app.llm.providers import PROVIDERS
from app.publish import publisher

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().ensure_dirs()
    init_db()
    worker.start()
    publisher.start()
    yield


app = FastAPI(title="PeakCut", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)
app.include_router(publish_router)
get_settings().ensure_dirs()
app.mount("/files", StaticFiles(directory=get_settings().renders_dir), name="files")


@app.get("/health")
def health():
    s = get_settings()
    version = ffmpeg.ffmpeg_version()
    return {
        "ok": version is not None,
        "ffmpeg": {"found": version is not None, "version": version,
                   "encoder": ffmpeg.video_encoder() if version else None},
        "providers": {
            name: {"label": p.label, "configured": bool(getattr(s, p.key_attr)),
                   "model": getattr(s, p.model_attr), "signup_url": p.signup_url}
            for name, p in PROVIDERS.items()
        },
        "llm_order": s.llm_order,
    }  # fmt: skip


class TestLLMRequest(BaseModel):
    provider: str


@app.post("/api/settings/test-llm")
def test_llm(req: TestLLMRequest):
    if req.provider not in PROVIDERS:
        return {"ok": False, "error": f"unknown provider {req.provider}"}
    try:
        data, used = chat_json(
            "You reply with JSON only.",
            'Reply with {"status": "ok", "model": "<your model name>"}',
            provider=req.provider,
        )
        return {"ok": True, "provider": used, "reply": data}
    except LLMError as e:
        return {"ok": False, "error": str(e)}
