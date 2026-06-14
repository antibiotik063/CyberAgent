from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from .models import NewsItem


logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "CS2": ["counter-strike 2", "cs2", "counter strike 2", "cs"],
    "Dota 2": ["dota 2", "the international", "esl one", "dreamleague"],
    "Fortnite": ["fortnite", "epic games"],
    "Valorant": ["valorant", "vct", "riot games"],
    "PUBG": ["pubg", "pubg mobile"],
    "Esports": ["esports", "киберспорт", "tournament", "турнир"],
}

SOURCE_DOMAINS = [
    "cybersport.ru",
    "cq.ru",
    "metaratings.ru",
    "playground.ru",
    "hltv.org",
    "liquipedia.net",
    "dexerto.com",
    "esportsinsider.com",
]


class NewsCollector:
    def __init__(self, max_items: int) -> None:
        self.max_items = max_items

    def fetch(self) -> list[NewsItem]:
        articles: list[NewsItem] = []
        for domain in SOURCE_DOMAINS:
            feed_url = self._google_news_rss(domain)
            try:
                feed = feedparser.parse(feed_url)
            except Exception as exc:
                logger.warning("Failed to parse feed for %s: %s", domain, exc)
                continue

            for entry in feed.entries:
                item = self._entry_to_news_item(entry, domain)
                if item is None:
                    continue
                articles.append(item)

        unique = self._dedupe(articles)
        unique.sort(key=lambda item: (item.score, item.published_at), reverse=True)
        return unique[: self.max_items]

    def _google_news_rss(self, domain: str) -> str:
        query = (
            f"site:{domain} (Counter-Strike 2 OR CS2 OR Dota 2 OR Fortnite OR "
            "Valorant OR PUBG OR esports OR tournament OR киберспорт)"
        )
        return (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=ru&gl=RU&ceid=RU:ru"
        )

    def _entry_to_news_item(self, entry, domain: str) -> NewsItem | None:
        title = unescape(getattr(entry, "title", "")).strip()
        summary_html = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = self._clean_html(summary_html)
        url = getattr(entry, "link", "").strip()

        published_struct = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if published_struct is None:
            published_at = datetime.now(timezone.utc)
        else:
            published_at = datetime(*published_struct[:6], tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - published_at > timedelta(hours=36):
            return None

        topic = self._topic_for_text(f"{title} {summary}")
        score = self._score_news(title, summary, topic, published_at)
        keywords = self._keywords(f"{title} {summary}")

        if not title or not url:
            return None

        return NewsItem(
            title=title,
            summary=summary,
            url=url,
            source=domain,
            published_at=published_at,
            topic=topic,
            score=score,
            keywords=keywords,
        )

    def _clean_html(self, value: str) -> str:
        text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text)

    def _topic_for_text(self, text: str) -> str:
        lower = text.lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                return topic
        return "Esports"

    def _score_news(
        self, title: str, summary: str, topic: str, published_at: datetime
    ) -> float:
        text = f"{title} {summary}".lower()
        score = 0.0
        hours_old = max((datetime.now(timezone.utc) - published_at).total_seconds() / 3600, 0.0)
        score += max(0, 24 - hours_old)
        score += 5 if topic in {"CS2", "Dota 2", "Valorant"} else 2
        score += 4 if any(word in text for word in ["win", "won", "champion", "signed", "patch"]) else 0
        score += 4 if any(word in text for word in ["турнир", "major", "vct", "blast", "esl"]) else 0
        score += 3 if any(word in text for word in ["россия", "russia", "cis"]) else 0
        return score

    def _keywords(self, text: str) -> list[str]:
        lowered = text.lower()
        found: list[str] = []
        for topic_keywords in TOPIC_KEYWORDS.values():
            for keyword in topic_keywords:
                if keyword in lowered and keyword not in found:
                    found.append(keyword)
        return found[:8]

    def _dedupe(self, items: list[NewsItem]) -> list[NewsItem]:
        seen_titles: set[str] = set()
        seen_urls: set[str] = set()
        unique: list[NewsItem] = []
        for item in items:
            normalized_title = re.sub(r"[^a-zа-я0-9]+", " ", item.title.lower()).strip()
            if item.url in seen_urls or normalized_title in seen_titles:
                continue
            seen_urls.add(item.url)
            seen_titles.add(normalized_title)
            unique.append(item)
        return unique
