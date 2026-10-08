"""Thin client for the Instagram API with Instagram Login (graph.instagram.com)."""

from datetime import datetime, timedelta, timezone

import httpx

BASE_URL = "https://graph.instagram.com"

PROFILE_FIELDS = "user_id,username,name,account_type,followers_count,follows_count,media_count"
MEDIA_FIELDS = (
    "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count"
)


class InstagramAPIError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _parse_insights(payload: dict) -> dict[str, float]:
    """Handle both `values` (time series / lifetime) and `total_value` shapes."""
    out: dict[str, float] = {}
    for item in payload.get("data", []):
        name = item.get("name")
        if "total_value" in item:
            out[name] = item["total_value"].get("value", 0)
        elif item.get("values"):
            value = item["values"][-1].get("value", 0)
            out[name] = value if isinstance(value, (int, float)) else 0
    return out


class InstagramClient:
    def __init__(
        self,
        access_token: str,
        api_version: str = "v23.0",
        user_id: str = "me",
        http: httpx.Client | None = None,
    ):
        self._token = access_token
        self._user = user_id
        self._http = http or httpx.Client(timeout=30)
        self._base = f"{BASE_URL}/{api_version}"

    def _get(self, url: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        if "access_token=" not in url:
            params["access_token"] = self._token
        if not url.startswith("http"):
            url = f"{self._base}/{url.lstrip('/')}"
        # httpx drops the URL's own query string when `params` is passed, which
        # would lose the cursor in `paging.next` URLs.
        resp = self._http.get(url, params=params or None)
        try:
            data = resp.json()
        except ValueError:
            raise InstagramAPIError(f"Non-JSON response ({resp.status_code})", resp.status_code)
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramAPIError(
                err.get("message", f"HTTP {resp.status_code}"), resp.status_code, err.get("code")
            )
        return data

    def _insights(self, path: str, metrics: list[str], params: dict | None = None) -> dict:
        """Request all metrics at once; if Meta rejects one, retry them one by one
        so a single deprecated metric does not break the whole call."""
        params = dict(params or {})
        try:
            return _parse_insights(self._get(path, {**params, "metric": ",".join(metrics)}))
        except InstagramAPIError:
            if len(metrics) == 1:
                raise
        out: dict[str, float] = {}
        for metric in metrics:
            try:
                out.update(_parse_insights(self._get(path, {**params, "metric": metric})))
            except InstagramAPIError:
                continue
        return out

    # --- profile & media -------------------------------------------------

    def get_profile(self) -> dict:
        return self._get(self._user, {"fields": PROFILE_FIELDS})

    def get_media(self, media_id: str) -> dict:
        return self._get(media_id, {"fields": MEDIA_FIELDS})

    def list_media(self, limit: int = 25) -> list[dict]:
        items: list[dict] = []
        data = self._get(f"{self._user}/media", {"fields": MEDIA_FIELDS, "limit": min(limit, 100)})
        while True:
            items.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")
            if len(items) >= limit or not next_url:
                break
            data = self._get(next_url)
        return items[:limit]

    def list_stories(self) -> list[dict]:
        """Only stories from the last 24 hours are returned by Meta."""
        return self._get(f"{self._user}/stories", {"fields": MEDIA_FIELDS}).get("data", [])

    # --- insights --------------------------------------------------------

    def get_media_insights(self, media_id: str, metrics: list[str]) -> dict[str, float]:
        return self._insights(f"{media_id}/insights", metrics)

    def get_account_insights(self, metrics: list[str], days: int = 28) -> dict[str, float]:
        """Totals over the last `days` days (Meta allows at most 30)."""
        days = max(1, min(days, 30))
        until = datetime.now(timezone.utc)
        since = until - timedelta(days=days)
        params = {
            "period": "day",
            "metric_type": "total_value",
            "since": int(since.timestamp()),
            "until": int(until.timestamp()),
        }
        return self._insights(f"{self._user}/insights", metrics, params)

    def get_audience(self, breakdown: str) -> list[dict]:
        """Follower demographics. Requires at least 100 followers."""
        data = self._get(
            f"{self._user}/insights",
            {
                "metric": "follower_demographics",
                "period": "lifetime",
                "metric_type": "total_value",
                "breakdown": breakdown,
            },
        )
        rows: list[dict] = []
        for item in data.get("data", []):
            for bd in item.get("total_value", {}).get("breakdowns", []):
                for r in bd.get("results", []):
                    rows.append({"value": " / ".join(r.get("dimension_values", [])), "count": r.get("value", 0)})
        return sorted(rows, key=lambda r: r["count"], reverse=True)

    def refresh_token(self) -> dict:
        """Extend a long-lived token by 60 days (token must be at least 24h old)."""
        return self._get(f"{BASE_URL}/refresh_access_token", {"grant_type": "ig_refresh_token"})
