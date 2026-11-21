"""Thin client for the Instagram Graph API.

Two ways in, same endpoints and metrics:
- `instagram`: Instagram Login (graph.instagram.com), token from the account's own credentials.
- `facebook`: Facebook Login (graph.facebook.com): a system user token from a business
  portfolio (Meta's default for new apps) or a Page token. Neither expires.

The token travels only in the Authorization header and never appears in URLs,
logs or error messages.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

# httpx logs every request URL at INFO level. The token never goes in the URL
# (see `_get`), but keep these loggers quiet anyway so MCP logs stay clean.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

BASE_URL = "https://graph.instagram.com"
HOSTS = {"instagram": BASE_URL, "facebook": "https://graph.facebook.com"}

PROFILE_FIELDS = {
    "instagram": "user_id,username,name,account_type,followers_count,follows_count,media_count",
    "facebook": "id,username,name,followers_count,follows_count,media_count",
}
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
        login: str = "instagram",
        http: httpx.Client | None = None,
    ):
        if login not in HOSTS:
            raise ValueError(f"login must be one of {tuple(HOSTS)}")
        self._token = access_token
        self._user = user_id
        self._login = login
        self._http = http or httpx.Client(timeout=30)
        self._base = f"{HOSTS[login]}/{api_version}"

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>") if self._token else text

    def _get(self, url: str, params: dict | None = None) -> dict:
        """GET with the token in the Authorization header, never in the URL, so it
        cannot end up in logs, tracebacks or error messages."""
        params = dict(params or {})
        if not url.startswith("http"):
            url = f"{self._base}/{url.lstrip('/')}"
        # `paging.next` URLs from Meta embed the token: strip it, the header carries it.
        parsed = httpx.URL(url)
        if "access_token" in parsed.params:
            url = str(parsed.copy_remove_param("access_token"))
        # httpx drops the URL's own query string when `params` is passed, which
        # would lose the cursor in `paging.next` URLs.
        try:
            resp = self._http.get(
                url,
                params=params or None,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        except httpx.HTTPError as e:
            # `from None`: the original exception carries the request, keep it out.
            raise InstagramAPIError(f"Network error: {type(e).__name__}") from None
        try:
            data = resp.json()
        except ValueError:
            raise InstagramAPIError(f"Non-JSON response ({resp.status_code})", resp.status_code) from None
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            raise InstagramAPIError(
                self._redact(err.get("message", f"HTTP {resp.status_code}")),
                resp.status_code,
                err.get("code"),
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
        return self._get(self._user, {"fields": PROFILE_FIELDS[self._login]})

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
        if self._login != "instagram":
            raise InstagramAPIError(
                "Only Instagram Login tokens need refreshing; Facebook Login tokens "
                "(system user or Page tokens) do not expire."
            )
        # The only call that needs the token as a parameter (Meta's spec for this
        # endpoint). httpx request logging is silenced above.
        return self._get(
            f"{BASE_URL}/refresh_access_token",
            {"grant_type": "ig_refresh_token", "access_token": self._token},
        )
