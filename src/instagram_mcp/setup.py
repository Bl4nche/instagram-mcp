"""Guided setup: each person stores their own token in their own settings file.

The token is read with a hidden prompt, checked against Meta, and written only to
the settings file (default ~/.instagram-mcp/.env). It is never printed, so the
setup can be run safely next to an AI assistant or in a shared terminal.
"""

import os
import re
import stat
from getpass import getpass
from pathlib import Path

from .client import InstagramAPIError, InstagramClient
from .config import USER_DIR

DEFAULTS = {"IG_API_VERSION": "v26.0", "IG_DB_PATH": "instagram_history.db"}


def settings_path() -> Path:
    explicit = os.getenv("IG_ENV_FILE", "").strip()
    return Path(explicit).expanduser() if explicit else USER_DIR / ".env"


def write_env(path: Path, values: dict[str, str]) -> None:
    """Set keys in an env file, keeping every other line, and make it owner-only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out = []
    for line in lines:
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=", line)
        if m and m.group(1) in pending:
            out.append(f"{m.group(1)}={pending.pop(m.group(1))}")
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in pending.items()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    # Owner read/write only (on Windows the user profile folder is already private).
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _ask(prompt: str, choices: tuple[str, ...]) -> str:
    while True:
        answer = input(prompt).strip()
        if answer in choices:
            return answer


def run_setup(api_version: str = DEFAULTS["IG_API_VERSION"]) -> int:
    path = settings_path()
    print("Instagram MCP setup")
    print(f"Your settings and history stay on this computer, in {path.parent}\n")
    print("How did you get your token? (see README, section 1)")
    print("  1) Instagram Login: token from 'API setup with Instagram login'")
    print("  2) Facebook Login: system user token (new Meta apps) or Page token")
    login = {"1": "instagram", "2": "facebook"}[_ask("Choice [1/2]: ", ("1", "2"))]

    user_id = "me"
    if login == "facebook":
        print("\nInstagram account ID: the number under the account name in the app's")
        print("'Generate access tokens' section (starts with 1784...).")
        while not re.fullmatch(r"\d{5,}", user_id):
            user_id = input("Instagram account ID: ").strip()

    token = ""
    while not token:
        token = getpass("\nPaste the token (input is hidden): ").strip()

    client = InstagramClient(token, api_version, user_id, login)
    try:
        profile = client.get_profile()
    except InstagramAPIError as e:
        print(f"\nMeta rejected the connection: {str(e).replace(token, '<token>')}")
        print("Nothing was saved. Check the token type, permissions and account ID, then retry.")
        return 1

    write_env(path, {"IG_LOGIN": login, "IG_ACCESS_TOKEN": token, "IG_USER_ID": user_id, **{
        k: v for k, v in DEFAULTS.items() if not _has_key(path, k)
    }})
    print(f"\nConnected to @{profile.get('username')} ({profile.get('followers_count')} followers).")
    print(f"Settings saved to {path} (owner-only). Restart Claude to use them.")
    return 0


def _has_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    return any(re.match(rf"\s*{key}\s*=", line) for line in path.read_text(encoding="utf-8").splitlines())
