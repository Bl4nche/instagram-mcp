"""Tests run against a fake Instagram API (httpx.MockTransport): no token needed."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from instagram_mcp.analytics import engagement_rates, rank
from instagram_mcp.client import InstagramAPIError, InstagramClient
from instagram_mcp.collector import take_snapshot
from instagram_mcp.storage import Storage

RECENT = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S+0000")

PROFILE = {"user_id": "1", "username": "agency", "followers_count": 1000, "follows_count": 50, "media_count": 3}
POSTS = [
    {"id": "p1", "media_product_type": "FEED", "media_type": "IMAGE", "timestamp": RECENT},
    {"id": "p2", "media_product_type": "REELS", "media_type": "VIDEO", "timestamp": RECENT},
    {"id": "p3", "media_product_type": "FEED", "media_type": "CAROUSEL_ALBUM", "timestamp": RECENT},
]
STORIES = [{"id": "s1", "media_product_type": "STORY", "media_type": "IMAGE", "timestamp": RECENT}]
DEPRECATED = {"impressions"}


def fake_api(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    q = request.url.params
    if path.endswith("/me"):
        return httpx.Response(200, json=PROFILE)
    if path.endswith("/me/media"):
        # two pages to exercise pagination
        if q.get("after") == "cursor2":
            return httpx.Response(200, json={"data": POSTS[2:]})
        nxt = "https://graph.instagram.com/v23.0/me/media?access_token=t&after=cursor2"
        return httpx.Response(200, json={"data": POSTS[:2], "paging": {"next": nxt}})
    if path.endswith("/me/stories"):
        return httpx.Response(200, json={"data": STORIES})
    if path.endswith("/insights"):
        metrics = q["metric"].split(",")
        if DEPRECATED & set(metrics):
            return httpx.Response(400, json={"error": {"message": "invalid metric", "code": 100}})
        return httpx.Response(
            200, json={"data": [{"name": m, "values": [{"value": 10}]} for m in metrics]}
        )
    return httpx.Response(404, json={"error": {"message": "not found"}})


@pytest.fixture
def client() -> InstagramClient:
    return InstagramClient("t", http=httpx.Client(transport=httpx.MockTransport(fake_api)))


def test_pagination_collects_all_pages(client):
    assert [m["id"] for m in client.list_media(10)] == ["p1", "p2", "p3"]
    assert len(client.list_media(2)) == 2


def test_deprecated_metric_is_skipped_not_fatal(client):
    result = client.get_media_insights("p1", ["reach", "impressions", "likes"])
    assert result == {"reach": 10, "likes": 10}


def test_single_bad_metric_raises(client):
    with pytest.raises(InstagramAPIError):
        client.get_media_insights("p1", ["impressions"])


def test_engagement_rates():
    rates = engagement_rates({"reach": 200, "likes": 10, "comments": 5, "shares": 3, "saved": 2}, 1000)
    assert rates == {"er_reach_pct": 10.0, "er_followers_pct": 2.0}
    assert engagement_rates({}, None) == {"er_reach_pct": None, "er_followers_pct": None}


def test_rank_by_metric_and_rate():
    items = [{"id": "a", "metrics": {"reach": 5}, "er_reach_pct": 9.0},
             {"id": "b", "metrics": {"reach": 50}, "er_reach_pct": 1.0}]
    assert rank(items, "reach", 1)[0]["id"] == "b"
    assert rank(items, "er_reach_pct", 1)[0]["id"] == "a"


def test_snapshot_builds_history_and_story_archive(client, tmp_path):
    store = Storage(tmp_path / "h.db")
    result = take_snapshot(client, store)
    assert (result["posts"], result["stories"], result["errors"]) == (3, 1, [])

    assert store.follower_history(1)[0]["followers"] == 1000
    archive = store.latest_metrics("STORY", days=1)
    assert [s["id"] for s in archive] == ["s1"]
    assert archive[0]["metrics"]["reach"] == 10
    assert {r["metric"] for r in store.metric_history("p2")} >= {"reach", "ig_reels_avg_watch_time"}
