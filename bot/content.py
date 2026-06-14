from __future__ import annotations

import json
import logging
from textwrap import dedent

from openai import OpenAI

from .models import NewsItem, PostDraft


logger = logging.getLogger(__name__)


class ContentGenerator:
    def __init__(self, api_key: str, text_model: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.text_model = text_model

    def generate_post(self, news_item: NewsItem) -> PostDraft:
        prompt = dedent(
            f"""
            Ты AI-контент-менеджер для Telegram-канала компьютерного клуба.
            На основе новости создай уникальный пост на русском языке.

            Требования:
            - живой, уверенный, понятный тон;
            - не копируй источник;
            - длина основного описания 420-700 символов;
            - объясни, почему это важно для игроков;
            - добавь 3-5 релевантных хэштегов;
            - верни только JSON с полями:
              headline, body, why_it_matters, hashtags, short_topic, image_prompt.

            Новость:
            Заголовок: {news_item.title}
            Источник: {news_item.source}
            Игра/тема: {news_item.topic}
            Краткое описание: {news_item.summary}
            Ссылка: {news_item.url}
            """
        ).strip()
        return self._run_prompt(prompt, mode="news")

    def generate_fallback_post(self) -> PostDraft:
        prompt = dedent(
            """
            Ты AI-контент-менеджер для Telegram-канала компьютерного клуба.
            Свежей уникальной новости нет, поэтому создай один fallback-пост на русском языке.

            Допустимые форматы:
            - факт дня по CS2, Dota 2, Fortnite или киберспорту;
            - полезный совет игрокам;
            - короткая турнирная подборка;
            - легкий развлекательный пост без токсичности.

            Требования:
            - живой и короткий Telegram-стиль;
            - 420-650 символов;
            - 3-5 релевантных хэштегов;
            - верни только JSON с полями:
              headline, body, why_it_matters, hashtags, short_topic, image_prompt.
            """
        ).strip()
        return self._run_prompt(prompt, mode="fallback")

    def _run_prompt(self, prompt: str, mode: str) -> PostDraft:
        response = self.client.responses.create(
            model=self.text_model,
            input=prompt,
        )
        raw_text = response.output_text
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Model returned non-JSON, using recovery parse: %s", exc)
            data = self._recover_json(raw_text)
        hashtags = [tag if tag.startswith("#") else f"#{tag}" for tag in data["hashtags"]]
        return PostDraft(
            mode=mode,
            headline=data["headline"].strip(),
            body=data["body"].strip(),
            why_it_matters=data["why_it_matters"].strip(),
            hashtags=hashtags[:5],
            short_topic=data["short_topic"].strip(),
            image_prompt=data["image_prompt"].strip(),
        )

    def _recover_json(self, raw_text: str) -> dict:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("OpenAI response does not contain JSON object.")
        return json.loads(raw_text[start : end + 1])
