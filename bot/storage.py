from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .models import NewsItem, PostDraft, PublicationResult


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    published_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    title TEXT NOT NULL,
                    topic_summary TEXT NOT NULL,
                    game TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    publication_status TEXT NOT NULL,
                    telegram_message_id INTEGER,
                    image_path TEXT,
                    raw_post TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT NOT NULL
                )
                """
            )

    def recent_posts(self, limit: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM publication_history
                ORDER BY datetime(published_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return list(rows)

    def log_run(self, status: str, details: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_logs (started_at, status, details)
                VALUES (?, ?, ?)
                """,
                (datetime.utcnow().isoformat(), status, details),
            )

    def store_publication(
        self,
        news_item: NewsItem | None,
        draft: PostDraft,
        result: PublicationResult,
    ) -> None:
        game = news_item.topic if news_item else draft.short_topic
        source = news_item.source if news_item else "fallback"
        source_url = news_item.url if news_item else "fallback"
        summary = news_item.summary if news_item else draft.body[:280]
        keywords = ",".join(news_item.keywords if news_item else draft.hashtags)
        raw_post = "\n\n".join(
            [
                draft.headline,
                draft.body,
                f"Почему это важно: {draft.why_it_matters}",
                " ".join(draft.hashtags),
            ]
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO publication_history (
                    published_at,
                    mode,
                    title,
                    topic_summary,
                    game,
                    source,
                    source_url,
                    keywords,
                    publication_status,
                    telegram_message_id,
                    image_path,
                    raw_post
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    draft.mode,
                    draft.headline,
                    summary,
                    game,
                    source,
                    source_url,
                    keywords,
                    "sent" if result.sent else f"failed:{result.error or 'unknown'}",
                    result.telegram_message_id,
                    str(result.image_path) if result.image_path else "",
                    raw_post,
                ),
            )
