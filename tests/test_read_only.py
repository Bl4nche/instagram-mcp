"""Safety net: this server must only ever READ from Meta.

These tests fail if a change introduces a request that could modify an account
(POST, PUT, PATCH, DELETE), or adds a client method nobody has checked.
"""

import inspect
import re
from pathlib import Path

import httpx
import pytest

from instagram_mcp.client import HOSTS, InstagramClient

SRC = Path(__file__).resolve().parents[1] / "src" / "instagram_mcp"

# Every public client method, with arguments to call it. A new method makes
# test_every_client_method_is_covered fail until it is added here.
CALLS = {
    "get_profile": (),
    "get_media": ("m1",),
    "list_media": (5,),
    "list_stories": (),
    "get_media_insights": ("m1", ["reach", "likes"]),
    "get_account_insights": (["reach"], 7),
    "get_audience": ("city",),
    "refresh_token": (),
}


def _recording_client(login: str) -> tuple[InstagramClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [], "access_token": "x", "expires_in": 0})

    client = InstagramClient("t", login=login, http=httpx.Client(transport=httpx.MockTransport(handler)))
    return client, seen


def test_every_client_method_is_covered():
    public = {
        name for name, fn in inspect.getmembers(InstagramClient, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == set(CALLS), (
        f"Uncovered client methods: {public - set(CALLS)}. "
        "Add them to CALLS so their HTTP method is checked."
    )


@pytest.mark.parametrize("login", sorted(HOSTS))
def test_client_only_sends_get_requests(login):
    client, seen = _recording_client(login)
    for name, args in CALLS.items():
        try:
            getattr(client, name)(*args)
        except Exception:
            pass  # e.g. refresh_token is refused in facebook mode, which is fine
    assert seen, "no request was made"
    assert {r.method for r in seen} == {"GET"}


def test_source_has_no_write_requests():
    """Catch write calls even in code paths the test above does not exercise."""
    pattern = re.compile(r"\.(post|put|patch|delete)\(|method\s*=\s*[\"'](POST|PUT|PATCH|DELETE)", re.I)
    offenders = [
        f"{path.name}:{n}: {line.strip()}"
        for path in SRC.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert not offenders, "Write requests found:\n" + "\n".join(offenders)
