from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    topic: str
    score: float = 0.0
    keywords: list[str] = field(default_factory=list)


@dataclass
class PostDraft:
    mode: str
    headline: str
    body: str
    why_it_matters: str
    hashtags: list[str]
    short_topic: str
    image_prompt: str


@dataclass
class PublicationResult:
    sent: bool
    telegram_message_id: int | None = None
    image_path: Path | None = None
    error: str | None = None
