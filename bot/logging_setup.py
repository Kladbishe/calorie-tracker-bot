import logging
import os
from logging.handlers import RotatingFileHandler

from bot.config import Settings


def configure_logging(settings: Settings) -> None:
    log_dir = os.path.dirname(settings.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        settings.log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
