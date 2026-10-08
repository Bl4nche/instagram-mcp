INTERACTION_METRICS = ("likes", "comments", "shares", "saved")


def interactions(metrics: dict[str, float]) -> float:
    if "total_interactions" in metrics:
        return metrics["total_interactions"]
    return sum(metrics.get(m, 0) for m in INTERACTION_METRICS)


def engagement_rates(metrics: dict[str, float], followers: int | None) -> dict[str, float | None]:
    """ER on reach (content quality) and ER on followers (industry-standard benchmark), in %."""
    total = interactions(metrics)
    reach = metrics.get("reach") or 0
    return {
        "er_reach_pct": round(total / reach * 100, 2) if reach else None,
        "er_followers_pct": round(total / followers * 100, 2) if followers else None,
    }


def rank(items: list[dict], by: str, top: int) -> list[dict]:
    """`by` is any metric name, or `er_reach_pct` / `er_followers_pct`."""
    def key(item: dict) -> float:
        value = item.get(by, item.get("metrics", {}).get(by))
        return value if value is not None else -1

    return sorted(items, key=key, reverse=True)[:top]
