"""Local SQLite history. The Instagram API only shows the present (and story
insights vanish after 24h), so snapshots are what make trends possible."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_snapshots (
    captured_at TEXT NOT NULL,
    username    TEXT,
    followers   INTEGER,
    follows     INTEGER,
    media_count INTEGER
);
CREATE TABLE IF NOT EXISTS media (
    id           TEXT PRIMARY KEY,
    product_type TEXT,
    media_type   TEXT,
    caption      TEXT,
    permalink    TEXT,
    posted_at    TEXT
);
CREATE TABLE IF NOT EXISTS media_metrics (
    media_id    TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       REAL,
    PRIMARY KEY (media_id, captured_at, metric)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_ts(ts: str | None) -> str | None:
    """Instagram returns `2026-10-01T12:00:00+0000`; store ISO 8601 UTC."""
    if not ts:
        return None
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).isoformat()


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()


class Storage:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def save_profile(self, profile: dict, captured_at: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO profile_snapshots VALUES (?, ?, ?, ?, ?)",
            (
                captured_at or now_iso(),
                profile.get("username"),
                profile.get("followers_count"),
                profile.get("follows_count"),
                profile.get("media_count"),
            ),
        )
        self.conn.commit()

    def upsert_media(self, media: dict) -> None:
        self.conn.execute(
            """INSERT INTO media VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET caption = excluded.caption,
                                             permalink = excluded.permalink""",
            (
                media["id"],
                media.get("media_product_type"),
                media.get("media_type"),
                media.get("caption"),
                media.get("permalink"),
                normalize_ts(media.get("timestamp")),
            ),
        )
        self.conn.commit()

    def save_metrics(self, media_id: str, metrics: dict[str, float], captured_at: str | None = None) -> None:
        ts = captured_at or now_iso()
        self.conn.executemany(
            "INSERT OR REPLACE INTO media_metrics VALUES (?, ?, ?, ?)",
            [(media_id, ts, k, v) for k, v in metrics.items()],
        )
        self.conn.commit()

    def follower_history(self, days: int = 90) -> list[dict]:
        rows = self.conn.execute(
            """SELECT captured_at, followers, follows, media_count FROM profile_snapshots
               WHERE captured_at >= ? ORDER BY captured_at""",
            (_cutoff(days),),
        ).fetchall()
        return [dict(r) for r in rows]

    def latest_metrics(self, product_type: str | None = None, days: int = 30) -> list[dict]:
        """Each media item with its most recent metric snapshot."""
        sql = """
            SELECT m.id, m.product_type, m.media_type, m.caption, m.permalink, m.posted_at,
                   mm.metric, mm.value
            FROM media m
            JOIN media_metrics mm ON mm.media_id = m.id
            WHERE m.posted_at >= ?
              AND mm.captured_at = (SELECT MAX(captured_at) FROM media_metrics WHERE media_id = m.id)
        """
        params: list = [_cutoff(days)]
        if product_type:
            sql += " AND m.product_type = ?"
            params.append(product_type.upper())
        sql += " ORDER BY m.posted_at DESC"

        items: dict[str, dict] = {}
        for r in self.conn.execute(sql, params):
            item = items.setdefault(
                r["id"],
                {k: r[k] for k in ("id", "product_type", "media_type", "caption", "permalink", "posted_at")}
                | {"metrics": {}},
            )
            item["metrics"][r["metric"]] = r["value"]
        return list(items.values())

    def metric_history(self, media_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT captured_at, metric, value FROM media_metrics WHERE media_id = ? ORDER BY captured_at",
            (media_id,),
        ).fetchall()
        return [dict(r) for r in rows]
