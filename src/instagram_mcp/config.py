import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Stable home for settings and history, used when the server runs as a Claude
# Code plugin (the plugin folder is replaced on every update, so nothing can
# live there).
USER_DIR = Path.home() / ".instagram-mcp"


@dataclass(frozen=True)
class Settings:
    access_token: str
    user_id: str
    api_version: str
    db_path: Path
    login: str = "instagram"


def env_file() -> Path | None:
    """Where settings come from, first match wins:
    IG_ENV_FILE, then ~/.instagram-mcp/.env, then a .env in the working folder."""
    explicit = os.getenv("IG_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    if (USER_DIR / ".env").is_file():
        return USER_DIR / ".env"
    found = find_dotenv(usecwd=True)
    return Path(found) if found else None


def load_settings() -> Settings:
    source = env_file()
    if source:
        load_dotenv(source)
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        where = source or USER_DIR / ".env"
        raise RuntimeError(
            f"IG_ACCESS_TOKEN is not set in {where}. Copy .env.example there and paste your token."
        )
    login = os.getenv("IG_LOGIN", "instagram").strip().lower() or "instagram"
    user_id = os.getenv("IG_USER_ID", "me").strip() or "me"
    if login == "facebook" and user_id == "me":
        raise RuntimeError(
            "With IG_LOGIN=facebook, IG_USER_ID must be the numeric Instagram account ID "
            "(see README, 'Option B')."
        )
    db_path = Path(os.getenv("IG_DB_PATH", "instagram_history.db")).expanduser()
    if not db_path.is_absolute() and source:
        # Keep the history next to the settings file, whatever the working folder.
        db_path = source.parent / db_path
    return Settings(
        access_token=token,
        user_id=user_id,
        api_version=os.getenv("IG_API_VERSION", "v26.0").strip(),
        db_path=db_path,
        login=login,
    )
