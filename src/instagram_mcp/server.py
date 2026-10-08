from functools import lru_cache

from mcp.server.mcpserver import MCPServer

from . import analytics
from .client import InstagramClient
from .collector import take_snapshot
from .config import load_settings
from .metrics import ACCOUNT_METRICS, AUDIENCE_BREAKDOWNS, metrics_for
from .storage import Storage

mcp = MCPServer("instagram")


@lru_cache
def _client() -> InstagramClient:
    s = load_settings()
    return InstagramClient(s.access_token, s.api_version, s.user_id)


@lru_cache
def _store() -> Storage:
    return Storage(load_settings().db_path)


# --- live data -----------------------------------------------------------


@mcp.tool()
def get_profile() -> dict:
    """Instagram profile: username, followers, following, number of posts."""
    return _client().get_profile()


@mcp.tool()
def list_media(limit: int = 25) -> list[dict]:
    """Latest posts and reels (caption, type, permalink, date, likes, comments)."""
    return _client().list_media(limit)


@mcp.tool()
def get_media_insights(media_id: str) -> dict:
    """Insights for one post, reel or story, plus engagement rates."""
    client = _client()
    media = client.get_media(media_id)
    insights = client.get_media_insights(media_id, metrics_for(media.get("media_product_type")))
    followers = client.get_profile().get("followers_count")
    return {"media": media, "insights": insights, **analytics.engagement_rates(insights, followers)}


@mcp.tool()
def get_account_insights(days: int = 28) -> dict:
    """Account totals over the last N days (max 30): reach, views, interactions,
    profile link taps, follows/unfollows."""
    return {"days": min(days, 30), "metrics": _client().get_account_insights(ACCOUNT_METRICS, days)}


@mcp.tool()
def get_audience(breakdown: str = "city") -> list[dict]:
    """Follower demographics. breakdown: age, gender, city or country.
    Requires at least 100 followers."""
    if breakdown not in AUDIENCE_BREAKDOWNS:
        raise ValueError(f"breakdown must be one of {AUDIENCE_BREAKDOWNS}")
    return _client().get_audience(breakdown)


@mcp.tool()
def top_posts(limit: int = 25, by: str = "er_reach_pct", top: int = 5) -> list[dict]:
    """Rank the latest `limit` posts by a metric (reach, views, saved, shares...)
    or by engagement rate (er_reach_pct, er_followers_pct)."""
    client = _client()
    followers = client.get_profile().get("followers_count")
    items = []
    for m in client.list_media(limit):
        insights = client.get_media_insights(m["id"], metrics_for(m.get("media_product_type")))
        items.append({**m, "metrics": insights, **analytics.engagement_rates(insights, followers)})
    return analytics.rank(items, by, top)


@mcp.tool()
def get_active_stories() -> list[dict]:
    """Stories published in the last 24 hours, with insights."""
    client = _client()
    return [
        {**s, "metrics": client.get_media_insights(s["id"], metrics_for("STORY"))}
        for s in client.list_stories()
    ]


# --- local history -------------------------------------------------------


@mcp.tool()
def snapshot(media_limit: int = 25) -> dict:
    """Save profile, recent posts and active stories with insights to the local
    history database. Usually run on a schedule, but can be triggered manually."""
    return take_snapshot(_client(), _store(), media_limit)


@mcp.tool()
def follower_history(days: int = 90) -> list[dict]:
    """Follower count over time, from saved snapshots."""
    return _store().follower_history(days)


@mcp.tool()
def story_archive(days: int = 30) -> list[dict]:
    """Past stories with their last saved insights. Instagram itself deletes
    story insights after 24h; this archive keeps them."""
    return _store().latest_metrics("STORY", days)


@mcp.tool()
def media_metric_history(media_id: str) -> list[dict]:
    """How a post's metrics grew across snapshots (e.g. reach on day 1 vs day 7)."""
    return _store().metric_history(media_id)
