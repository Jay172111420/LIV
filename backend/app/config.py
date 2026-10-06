"""Application settings, loaded from environment variables (prefix LIV_) or a .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LIV_", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite:///./liv.db"
    session_cookie_name: str = "liv_session"
    session_ttl_hours: int = 24 * 14
    # Set to true whenever the app is served over HTTPS.
    cookie_secure: bool = False
    # Extra origins (comma separated) allowed to make state-changing requests.
    allowed_origins: str = ""
    seed_on_startup: bool = True
    frontend_dir: Path = PROJECT_ROOT / "frontend"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
