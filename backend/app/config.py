"""App settings, loaded from the repo-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # speech-to-text
    groq_api_key: str = ""
    siliconflow_api_key: str = ""
    local_whisper_model: str = "small"

    # LLMs
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4.5-flash"
    siliconflow_model: str = "Qwen/Qwen3-8B"
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    llm_order: str = "zhipu,siliconflow,groq,openrouter,gemini"

    # YouTube access (only needed if YouTube shows "confirm you're not a bot")
    ytdlp_cookies_from_browser: str = ""  # firefox | edge | chrome | brave
    ytdlp_cookies_file: str = ""  # path to an exported cookies.txt

    # rendering
    video_encoder: str = "auto"
    default_clip_count: int = 8
    min_clip_seconds: int = 15
    max_clip_seconds: int = 60
    # videos longer than this only get their most-replayed stretch analyzed (Groq free ~8h audio/day)
    max_analyze_seconds: int = 7200

    # publishing
    youtube_client_secret_file: str = "backend/tokens/client_secret.json"
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_graph_version: str = "v23.0"

    # app
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"
    data_dir: Path = ROOT_DIR / "data"

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "peakcut.db"

    def ensure_dirs(self) -> None:
        for d in (self.downloads_dir, self.cache_dir, self.renders_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
