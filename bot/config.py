from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env.local")
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    openai_api_key: str
    timezone: str = "Europe/Moscow"
    post_time: str = "09:00"
    openai_text_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-2"
    club_logo_path: Path = Path("D:/логоклуб/Logo RW.png")
    history_limit: int = 30
    max_news_items: int = 10
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    logs_dir: Path = ROOT_DIR / "logs"
    generated_dir: Path = ROOT_DIR / "generated"
    database_path: Path = ROOT_DIR / "data" / "bot.sqlite3"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required.")
    return value


def load_settings() -> Settings:
    settings = Settings(
        telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_required("TELEGRAM_CHANNEL_ID"),
        openai_api_key=_required("OPENAI_API_KEY"),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow"),
        post_time=os.getenv("POST_TIME", "09:00"),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
        openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        club_logo_path=Path(os.getenv("CLUB_LOGO_PATH", "D:/логоклуб/Logo RW.png")),
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    return settings
