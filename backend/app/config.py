from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://rxflow:rxflow_local_only@localhost:5432/rxflow"
    admin_api_key: str = ""
    seed_orders: int = 30000
    model_dir: Path = Path("artifacts")
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
