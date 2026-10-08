"""Entry point.

    instagram-mcp                 run the MCP server (stdio)
    instagram-mcp snapshot        save a snapshot (for cron / Task Scheduler)
    instagram-mcp refresh-token   extend the access token by 60 days
"""

import argparse
import json
from datetime import datetime, timedelta


def main() -> None:
    parser = argparse.ArgumentParser(prog="instagram-mcp")
    sub = parser.add_subparsers(dest="command")
    snap = sub.add_parser("snapshot", help="save profile, posts and stories insights")
    snap.add_argument("--limit", type=int, default=25, help="number of recent posts")
    sub.add_parser("refresh-token", help="extend the long-lived token")
    args = parser.parse_args()

    if args.command is None:
        from .server import mcp

        mcp.run()
        return

    from .client import InstagramClient
    from .config import load_settings

    s = load_settings()
    client = InstagramClient(s.access_token, s.api_version, s.user_id)

    if args.command == "snapshot":
        from .collector import take_snapshot
        from .storage import Storage

        print(json.dumps(take_snapshot(client, Storage(s.db_path), args.limit), indent=2))
    elif args.command == "refresh-token":
        data = client.refresh_token()
        expires = datetime.now() + timedelta(seconds=data.get("expires_in", 0))
        print("New token (paste it into .env as IG_ACCESS_TOKEN):\n")
        print(data["access_token"])
        print(f"\nExpires: {expires:%Y-%m-%d}")


if __name__ == "__main__":
    main()
