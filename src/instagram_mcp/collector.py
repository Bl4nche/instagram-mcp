from .client import InstagramAPIError, InstagramClient
from .metrics import metrics_for
from .storage import Storage, now_iso


def take_snapshot(client: InstagramClient, store: Storage, media_limit: int = 25) -> dict:
    """Save profile counters, recent posts and active stories with their insights.

    Run it every few hours (see README) so no story is lost: Meta deletes story
    insights 24 hours after publishing.
    """
    captured_at = now_iso()
    store.save_profile(client.get_profile(), captured_at)

    saved = {"posts": 0, "stories": 0, "errors": []}
    for kind, items in (("posts", client.list_media(media_limit)), ("stories", client.list_stories())):
        for media in items:
            store.upsert_media(media)
            try:
                insights = client.get_media_insights(media["id"], metrics_for(media.get("media_product_type")))
            except InstagramAPIError as e:
                saved["errors"].append(f"{media['id']}: {e}")
                continue
            store.save_metrics(media["id"], insights, captured_at)
            saved[kind] += 1
    return {"captured_at": captured_at, **saved}
