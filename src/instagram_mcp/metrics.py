"""Metric lists per content type.

Meta renames and deprecates metrics often (e.g. `impressions` and `video_views`
were replaced by `views` in 2025). Edit these lists instead of the client code.
Unsupported metrics are skipped automatically at runtime.
"""

MEDIA_METRICS: dict[str, list[str]] = {
    "FEED": ["reach", "views", "likes", "comments", "shares", "saved", "total_interactions"],
    "REELS": [
        "reach", "views", "likes", "comments", "shares", "saved", "total_interactions",
        "ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
    ],
    "STORY": [
        "reach", "views", "replies", "shares", "total_interactions",
        "follows", "profile_visits", "navigation",
    ],
}

ACCOUNT_METRICS: list[str] = [
    "reach", "views", "accounts_engaged", "total_interactions", "likes", "comments",
    "shares", "saves", "replies", "profile_links_taps", "follows_and_unfollows",
]

AUDIENCE_BREAKDOWNS = ("age", "gender", "city", "country")


def metrics_for(product_type: str | None) -> list[str]:
    """`AD` and unknown types fall back to feed metrics."""
    return MEDIA_METRICS.get((product_type or "FEED").upper(), MEDIA_METRICS["FEED"])
