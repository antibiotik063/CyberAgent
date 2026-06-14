from __future__ import annotations

from pathlib import Path

import requests

from .models import PostDraft, PublicationResult


class TelegramPublisher:
    def __init__(self, bot_token: str, channel_id: str) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def publish(self, draft: PostDraft, image_path: Path | None = None) -> PublicationResult:
        caption = self._render_caption(draft)
        if image_path and image_path.exists():
            photo_caption = caption if len(caption) <= 1024 else self._render_short_photo_caption(draft)
            with image_path.open("rb") as image_file:
                response = requests.post(
                    f"{self.base_url}/sendPhoto",
                    data={
                        "chat_id": self.channel_id,
                        "caption": photo_caption,
                        "parse_mode": "HTML",
                    },
                    files={"photo": image_file},
                    timeout=90,
                )
        else:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                data={
                    "chat_id": self.channel_id,
                    "text": caption,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=60,
            )

        payload = response.json()
        if response.ok and payload.get("ok"):
            message_id = payload["result"]["message_id"]
            if image_path and image_path.exists() and len(caption) > 1024:
                extra = requests.post(
                    f"{self.base_url}/sendMessage",
                    data={
                        "chat_id": self.channel_id,
                        "text": caption,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=60,
                )
                extra_payload = extra.json()
                if not extra.ok or not extra_payload.get("ok"):
                    return PublicationResult(
                        sent=False,
                        image_path=image_path,
                        error=extra_payload.get("description", extra.text),
                    )
            return PublicationResult(sent=True, telegram_message_id=message_id, image_path=image_path)

        return PublicationResult(
            sent=False,
            image_path=image_path,
            error=payload.get("description", response.text),
        )

    def _render_caption(self, draft: PostDraft) -> str:
        hashtags = " ".join(draft.hashtags)
        return (
            f"<b>{draft.headline}</b>\n\n"
            f"{draft.body}\n\n"
            f"<b>Почему это важно:</b> {draft.why_it_matters}\n\n"
            f"{hashtags}"
        )

    def _render_short_photo_caption(self, draft: PostDraft) -> str:
        hashtags = " ".join(draft.hashtags[:3])
        return f"<b>{draft.headline}</b>\n\n{hashtags}"
