"""Safety net: the access token must never leave the Authorization header.

URLs end up in logs (httpx logs every request) and error messages end up in
the MCP client's context, so neither may contain the token.
"""

import logging

import httpx
import pytest

from instagram_mcp.client import HOSTS, InstagramAPIError, InstagramClient

from test_read_only import CALLS

SECRET = "SECRET-TOKEN-123"


def _client(handler, login="instagram") -> InstagramClient:
    return InstagramClient(SECRET, login=login, http=httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("login", sorted(HOSTS))
def test_token_only_in_header(login):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [], "access_token": "x", "expires_in": 0})

    client = _client(handler, login)
    for name, args in CALLS.items():
        if name == "refresh_token":
            continue  # Meta requires the token as a parameter there; logging is silenced
        try:
            getattr(client, name)(*args)
        except InstagramAPIError:
            pass
    assert seen
    for request in seen:
        assert SECRET not in str(request.url)
        assert request.headers["Authorization"] == f"Bearer {SECRET}"


def test_token_stripped_from_paging_urls():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if request.url.params.get("after") == "c2":
            return httpx.Response(200, json={"data": [{"id": "2"}]})
        nxt = f"https://graph.instagram.com/v26.0/me/media?access_token={SECRET}&after=c2"
        return httpx.Response(200, json={"data": [{"id": "1"}], "paging": {"next": nxt}})

    assert [m["id"] for m in _client(handler).list_media(10)] == ["1", "2"]
    assert all(SECRET not in str(r.url) for r in seen)


def test_api_error_message_is_redacted():
    def handler(request):
        return httpx.Response(400, json={"error": {"message": f"bad token {SECRET}", "code": 190}})

    with pytest.raises(InstagramAPIError) as exc:
        _client(handler).get_profile()
    assert SECRET not in str(exc.value)
    assert exc.value.code == 190


def test_network_error_does_not_carry_the_request():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(InstagramAPIError) as exc:
        _client(handler).get_profile()
    assert SECRET not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


def test_httpx_request_logging_is_silenced():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_write_env_keeps_other_lines(tmp_path):
    from instagram_mcp.setup import write_env

    env = tmp_path / "sub" / ".env"
    env.parent.mkdir()
    env.write_text("# comment\nIG_ACCESS_TOKEN=old\nIG_DB_PATH=h.db\n", encoding="utf-8")
    write_env(env, {"IG_ACCESS_TOKEN": "new", "IG_LOGIN": "facebook"})
    assert env.read_text(encoding="utf-8").splitlines() == [
        "# comment", "IG_ACCESS_TOKEN=new", "IG_DB_PATH=h.db", "IG_LOGIN=facebook",
    ]


@pytest.mark.parametrize("ok", [True, False])
def test_setup_never_prints_the_token(monkeypatch, tmp_path, capsys, ok):
    from instagram_mcp import setup

    env = tmp_path / ".env"
    monkeypatch.setenv("IG_ENV_FILE", str(env))
    answers = iter(["2", "17841400000000000"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(setup, "getpass", lambda _: SECRET)

    def get_profile(self):
        if not ok:
            raise InstagramAPIError(f"invalid {SECRET}")
        return {"username": "someone", "followers_count": 5}

    monkeypatch.setattr(InstagramClient, "get_profile", get_profile)
    assert setup.run_setup() == (0 if ok else 1)
    out = capsys.readouterr().out
    assert SECRET not in out
    if ok:
        text = env.read_text(encoding="utf-8")
        assert f"IG_ACCESS_TOKEN={SECRET}" in text and "IG_LOGIN=facebook" in text
        assert "@someone" in out
    else:
        assert not env.exists()
