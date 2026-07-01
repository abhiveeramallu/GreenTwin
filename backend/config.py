from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_SQLITE_PATH = (DATA_DIR / "greentwin.db").resolve()

GREENHOUSE_PROFILES = {
    "small": {
        "label": "Small",
        "k": 0.4,
        "s": 0.25,
        "w": 0.08,
        "description": "Warms up quickly, responds sharply to solar gain, and has light wind buffering.",
    },
    "medium": {
        "label": "Medium",
        "k": 0.3,
        "s": 0.2,
        "w": 0.1,
        "description": "Balanced profile used as the default digital twin configuration.",
    },
    "large": {
        "label": "Large",
        "k": 0.2,
        "s": 0.15,
        "w": 0.15,
        "description": "Higher thermal inertia with stronger wind-assisted passive cooling.",
    },
}


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _split_csv(raw_value: str | None, fallback: list[str]) -> list[str]:
    if not raw_value:
        return fallback
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or fallback


def _normalize_database_url(raw_value: str) -> str:
    value = raw_value.strip()
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://") and not value.startswith("postgresql+"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str
    api_prefix: str
    default_location: str
    default_weather_provider: str
    default_greenhouse_type: str
    default_target_temp_c: float
    default_poll_interval_seconds: int
    database_url: str
    weatherapi_key: str | None
    openweathermap_key: str | None
    cors_origins: list[str]
    enable_background_polling: bool
    enable_log_storage: bool
    weather_timeout_seconds: float


_load_env_file(PROJECT_ROOT / ".env")


settings = Settings(
    app_name=os.getenv("GREENTWIN_APP_NAME", "GreenTwin AI"),
    api_prefix=os.getenv("GREENTWIN_API_PREFIX", "/api/v1"),
    default_location=os.getenv("DEFAULT_LOCATION", "Coimbatore, India"),
    default_weather_provider=os.getenv("WEATHER_PROVIDER", "weatherapi").strip().lower(),
    default_greenhouse_type=os.getenv("GREENHOUSE_TYPE", "medium").strip().lower(),
    default_target_temp_c=float(os.getenv("TARGET_TEMPERATURE_C", "28")),
    default_poll_interval_seconds=max(30, int(os.getenv("GREENTWIN_POLL_INTERVAL_SECONDS", "60"))),
    database_url=_normalize_database_url(os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")),
    weatherapi_key=os.getenv("WEATHERAPI_KEY"),
    openweathermap_key=os.getenv("OPENWEATHERMAP_API_KEY"),
    cors_origins=_split_csv(
        os.getenv("GREENTWIN_CORS_ORIGINS"),
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
    ),
    enable_background_polling=os.getenv("GREENTWIN_ENABLE_BACKGROUND_POLLING", "true").strip().lower()
    not in {"0", "false", "no"},
    enable_log_storage=os.getenv("GREENTWIN_ENABLE_LOG_STORAGE", "true").strip().lower() not in {"0", "false", "no"},
    weather_timeout_seconds=float(os.getenv("GREENTWIN_WEATHER_TIMEOUT_SECONDS", "12")),
)
