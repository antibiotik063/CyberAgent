from __future__ import annotations

import argparse
import logging

from bot.config import load_settings
from bot.runner import BotRunner


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler("logs/bot.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Telegram esports content bot.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single collection/generation/publication cycle immediately.",
    )
    return parser.parse_args()


def main() -> None:
    settings = load_settings()
    configure_logging()
    runner = BotRunner(settings)
    args = parse_args()

    if args.once:
        runner.run_once()
        return

    runner.run_scheduler()


if __name__ == "__main__":
    main()
