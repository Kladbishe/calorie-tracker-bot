from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    encryption_key: str

    openai_text_model: str = "gpt-4o"
    openai_vision_model: str = "gpt-4o"

    database_path: str = "./data/bot.db"

    weekly_weight_check_day: str = "sunday"
    weekly_weight_check_time: str = "10:00"

    timezone: str = "UTC"

    log_level: str = "INFO"
    log_file: str = "./logs/bot.log"

    admin_telegram_ids: list[int] = []

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        # pydantic-settings tries json.loads on env values for list-typed fields first, so a
        # single ID with no comma (valid JSON as a bare int) arrives as `int`, not `str`.
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(part) for part in value.split(",") if part.strip()]
        return value


def load_settings() -> Settings:
    return Settings()
