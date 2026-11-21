"""Entry point.

    instagram-mcp                 run the MCP server (stdio)
    instagram-mcp setup           connect your own account (token stays on your computer)
    instagram-mcp check           show which account is connected
    instagram-mcp snapshot        save a snapshot (for cron / Task Scheduler)
    instagram-mcp refresh-token   extend an Instagram Login token by 60 days

No command ever prints the access token.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta


def main() -> None:
    parser = argparse.ArgumentParser(prog="instagram-mcp")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("setup", help="connect your Instagram account (interactive)")
    sub.add_parser("check", help="show the connected account")
    snap = sub.add_parser("snapshot", help="save profile, posts and stories insights")
    snap.add_argument("--limit", type=int, default=25, help="number of recent posts")
    sub.add_parser("refresh-token", help="extend an Instagram Login token by 60 days")
    args = parser.parse_args()

    if args.command is None:
        from .server import mcp

        mcp.run()
        return

    if args.command == "setup":
        from .setup import run_setup

        sys.exit(run_setup())

    from .client import InstagramClient
    from .config import env_file, load_settings

    s = load_settings()
    client = InstagramClient(s.access_token, s.api_version, s.user_id, s.login)

    if args.command == "check":
        p = client.get_profile()
        print(f"Connected to @{p.get('username')} ({p.get('followers_count')} followers)")
        print(f"Login: {s.login} | settings: {env_file()} | history: {s.db_path}")
    elif args.command == "snapshot":
        from .collector import take_snapshot
        from .storage import Storage

        print(json.dumps(take_snapshot(client, Storage(s.db_path), args.limit), indent=2))
    elif args.command == "refresh-token":
        if s.login == "facebook":
            print("Nothing to do: Facebook Login tokens do not expire.")
            return
        from .setup import settings_path, write_env

        target = env_file() or settings_path()
        data = client.refresh_token()
        write_env(target, {"IG_ACCESS_TOKEN": data["access_token"]})
        expires = datetime.now() + timedelta(seconds=data.get("expires_in", 0))
        print(f"Token renewed and saved to {target}. Expires: {expires:%Y-%m-%d}")


if __name__ == "__main__":
    main()
