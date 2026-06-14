from __future__ import annotations

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Settings
from .content import ContentGenerator
from .images import ImageGenerator
from .models import NewsItem, PostDraft
from .news import NewsCollector
from .storage import Storage
from .telegram_client import TelegramPublisher


logger = logging.getLogger(__name__)


class BotRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = Storage(settings.database_path)
        self.collector = NewsCollector(settings.max_news_items)
        self.content = ContentGenerator(settings.openai_api_key, settings.openai_text_model)
        self.images = ImageGenerator(settings)
        self.publisher = TelegramPublisher(
            settings.telegram_bot_token,
            settings.telegram_channel_id,
        )

    def run_once(self) -> None:
        try:
            news_items = self.collector.fetch()
            self.storage.log_run("news_fetched", f"Collected {len(news_items)} items")
            selected_item = self._select_unique_news(news_items)
            draft = (
                self.content.generate_post(selected_item)
                if selected_item
                else self.content.generate_fallback_post()
            )
            image_path = None
            try:
                image_path = self.images.generate(draft)
            except Exception as image_exc:
                logger.exception("Image generation failed: %s", image_exc)
                self.storage.log_run("image_failed", str(image_exc))

            result = self.publisher.publish(draft, image_path)
            self.storage.store_publication(selected_item, draft, result)
            if not result.sent:
                raise RuntimeError(result.error or "Telegram publish failed")
            self.storage.log_run(
                "published",
                f"mode={draft.mode}; title={draft.headline}; message_id={result.telegram_message_id}",
            )
        except Exception as exc:
            logger.exception("Bot run failed: %s", exc)
            self.storage.log_run("failed", str(exc))
            raise

    def run_scheduler(self) -> None:
        hour, minute = self._parse_post_time(self.settings.post_time)
        scheduler = BlockingScheduler(timezone=ZoneInfo(self.settings.timezone))
        scheduler.add_job(
            self.run_once,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_content_publication",
            replace_existing=True,
        )
        logger.info(
            "Scheduler started for %s daily at %02d:%02d",
            self.settings.timezone,
            hour,
            minute,
        )
        scheduler.start()

    def _select_unique_news(self, items: list[NewsItem]) -> NewsItem | None:
        history = self.storage.recent_posts(self.settings.history_limit)
        for item in items:
            if not self._is_duplicate(item, history):
                return item
        return None

    def _is_duplicate(self, item: NewsItem, history: list) -> bool:
        normalized_title = self._normalize(item.title)
        normalized_url = item.url.strip().lower()
        for row in history:
            if normalized_url and normalized_url == row["source_url"].strip().lower():
                return True
            if normalized_title == self._normalize(row["title"]):
                return True
            if self._jaccard(normalized_title, self._normalize(row["title"])) >= 0.75:
                return True
            summary_pair = f"{item.topic} {item.summary}"
            if self._jaccard(self._normalize(summary_pair), self._normalize(row["topic_summary"])) >= 0.8:
                return True
        return False

    def _normalize(self, value: str) -> str:
        return re.sub(r"[^a-zа-я0-9]+", " ", value.lower()).strip()

    def _jaccard(self, left: str, right: str) -> float:
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def _parse_post_time(self, value: str) -> tuple[int, int]:
        hour_str, minute_str = value.split(":")
        return int(hour_str), int(minute_str)
