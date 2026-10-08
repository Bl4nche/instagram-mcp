import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    access_token: str
    user_id: str
    api_version: str
    db_path: Path


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "IG_ACCESS_TOKEN is not set. Copy .env.example to .env and paste your token."
        )
    return Settings(
        access_token=token,
        user_id=os.getenv("IG_USER_ID", "me").strip() or "me",
        api_version=os.getenv("IG_API_VERSION", "v23.0").strip(),
        db_path=Path(os.getenv("IG_DB_PATH", "instagram_history.db")),
    )
