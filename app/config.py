from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://reels:reels@postgres:5432/reels"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "reelsadmin"
    minio_secret_key: str = "reelsadmin123"
    minio_bucket: str = "reels-factory"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_text_model: str = "gpt-4.1-mini"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    openai_tts_speed: float = 0.94
    pexels_api_key: str = ""
    default_topic: str = "AI ในโรงพยาบาล"
    default_language: str = "th"
    default_target_seconds: int = 45
    work_dir: Path = Path("/data/jobs")
    tz: str = "Asia/Bangkok"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
