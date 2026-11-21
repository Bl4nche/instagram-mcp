# instagram-mcp

An [MCP](https://modelcontextprotocol.io) server that lets Claude (or any MCP client) analyze **organic Instagram performance**: posts, reels, stories, account reach and audience.

What makes it different from a plain API wrapper is the **local history**:

- Instagram deletes **story insights 24 hours** after publishing → this server archives them.
- The API only shows current follower counts → snapshots build a **follower growth curve**.
- Post metrics keep changing → you can see how reach grew from day 1 to day 7.

> Ask things like: *"Which reels had the best engagement rate this month?"*, *"How did my stories perform last week?"*, *"Where are my followers from?"*

## Tools

| Tool | Source | What it does |
|---|---|---|
| `get_profile` | API | Username, followers, following, post count |
| `list_media` | API | Latest posts and reels |
| `get_media_insights` | API | Reach, views, likes, comments, shares, saves + engagement rate |
| `get_account_insights` | API | Account totals over the last N days (max 30) |
| `get_audience` | API | Follower demographics by age, gender, city, country |
| `top_posts` | API | Rank posts by any metric or by engagement rate |
| `get_active_stories` | API | Stories from the last 24h with insights |
| `snapshot` | API → DB | Save profile, posts and stories to the local history |
| `follower_history` | DB | Follower count over time |
| `story_archive` | DB | Past stories with their insights |
| `media_metric_history` | DB | How a post's metrics evolved across snapshots |

Engagement rate is reported two ways: on **reach** (`er_reach_pct`, content quality) and on **followers** (`er_followers_pct`, the usual benchmark).

## Privacy

Everyone uses **their own** Meta app, token and account. Nothing is shared, and nothing in this repository belongs to anyone's account.

- **Your token and data stay on your computer**, in `~/.instagram-mcp/` (`.env` for settings, `instagram_history.db` for history). That folder is outside the repository, so it is never committed or published. On macOS/Linux the settings file is made readable by you only.
- **The server only talks to Meta** (`graph.facebook.com` or `graph.instagram.com`). There is no telemetry and no other server.
- **The token is never shown**: it travels in the request header (never in URLs, so it cannot end up in logs), error messages are redacted, and no command prints it. `setup` reads it with a hidden prompt, so you never need to paste it into a chat with an AI assistant.
- **Read-only**: the server never posts, comments, sends messages or deletes anything. A test (`tests/test_read_only.py`) fails if a request that could change an account is added.
- Insights are sent to the AI client you connect (e.g. Claude) when you ask about them, like any MCP tool output.

## Requirements

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- An Instagram **Business or Creator** account (personal profiles are not supported by the API; switching is free in the Instagram app, *Settings → Account type and tools*)
- A Facebook account to sign in to [Meta for Developers](https://developers.facebook.com) (it does not need to be linked to Instagram)

## 1. Create your Meta app and get a token

Each person creates their own app: it is free, and while it stays in **development mode** no App Review is needed for your own account.

### New apps (unified login, recommended)

Meta now creates new Instagram apps with "unified login". The token is a **system user token that does not expire**.

1. On [developers.facebook.com/apps](https://developers.facebook.com/apps) click **Create app**. In *Use cases*, open the **Content management** filter and choose **Manage messaging & content on Instagram**. If asked, skip linking a business portfolio for now.
2. **Business portfolio.** In the Instagram use case (**Customize → API setup with Unified login**), link a business portfolio, or create one for yourself in [Meta Business Suite](https://business.facebook.com) (free, no Facebook Page needed). Then add your Instagram account to it: Business Suite → **Settings → Accounts → Instagram accounts → Add**.
3. **Tester.** In **App roles → Roles → Add people**, add your Instagram username as **Instagram tester**, then accept the invite on Instagram (*Settings → Website permissions / Apps and websites → Tester invites*, or `instagram.com/accounts/manage_access`).
4. **Permissions.** In the Instagram use case → **Permissions and features**, add only `instagram_basic` and `instagram_manage_insights`. Leave out publishing, messaging, comments and ads.
5. **Configuration.** In **Facebook Login for Business → Configurations → Create configuration** (not "from template": the template has no insights permission), choose variant *General*, token *System user access token*, expiry *Never*, asset *Instagram account*, and the two permissions above.
6. **Token.** Back in **API setup with Unified login**: step 1 shows your configuration as *Compatible*; in step 2 click **Generate token** next to your account and copy it. Note the account ID shown under the username (it starts with `1784…`). Skip redirect URLs, webhooks and app review: they are only needed if other people log in through your app.

Then run `instagram-mcp setup` (below) and choose **2) Facebook Login**.

### Apps with "API setup with Instagram login"

Older apps may still show this tab. There, under *Generate access tokens*, **Add account**, log in with Instagram, check that `instagram_business_basic` and `instagram_business_manage_insights` are granted, and **Generate token**. This token lasts **60 days** (see *Token renewal*). In `setup` choose **1) Instagram Login**.

### Page token (Instagram account linked to a Facebook Page)

If you manage the account through a Facebook Page, a Page token from the [Graph API Explorer](https://developers.facebook.com/tools/explorer) also works and does not expire: get a user token with `pages_show_list`, `pages_read_engagement`, `instagram_basic`, `instagram_manage_insights`, `business_management`, extend it in the Access Token Tool, then query `<PAGE_ID>?fields=access_token`. Find the Instagram account ID with `me/accounts?fields=instagram_business_account{id,username}`. In `setup` choose **2) Facebook Login**. Explorer responses contain your token inside `paging` URLs: don't paste them anywhere.

Revoke access at any time by removing the app from your business portfolio or from Facebook **Settings → Business integrations**.

## 2. Install and connect your account

```bash
git clone https://github.com/<your-username>/instagram-mcp.git
cd instagram-mcp
uv sync
uv run instagram-mcp setup
```

`setup` asks for the login type, the account ID (Facebook Login only) and the token (hidden input), checks them against Meta and saves them to `~/.instagram-mcp/.env`. Nothing is saved if Meta rejects them. Run it in your own terminal, not through an AI assistant.

Check the connection at any time (shows the account, never the token):

```bash
uv run instagram-mcp check
```

## 3. Connect it to Claude

**Claude Code plugin (server + skill)**

The repo is also a Claude Code plugin: it starts the MCP server and adds the `instagram` skill, which tells Claude how to use the tools and read the numbers.

```bash
claude plugin marketplace add /absolute/path/to/instagram-mcp
claude plugin install instagram@instagram-mcp
```

The plugin reads your settings from `~/.instagram-mcp/.env` (created by `setup`), never from the plugin folder, which is replaced on every update. Settings are looked up in this order: `IG_ENV_FILE`, `~/.instagram-mcp/.env`, `.env` in the working folder.

**Claude Code (server only)**

```bash
claude mcp add instagram -- uv run --directory /absolute/path/to/instagram-mcp instagram-mcp
```

**Claude Desktop** (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "instagram": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/instagram-mcp", "instagram-mcp"]
    }
  }
}
```

## 4. Schedule snapshots (recommended)

Run a snapshot **every 6 hours** so no story is lost.

**macOS / Linux** (`crontab -e`):

```
0 */6 * * * cd /path/to/instagram-mcp && uv run instagram-mcp snapshot >> snapshot.log 2>&1
```

**Windows** (PowerShell, once):

```powershell
$action  = New-ScheduledTaskAction -Execute "uv" -Argument "run instagram-mcp snapshot" -WorkingDirectory "C:\path\to\instagram-mcp"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 6)
Register-ScheduledTask -TaskName "instagram-mcp-snapshot" -Action $action -Trigger $trigger
```

## Token renewal

System user and Page tokens do not expire. Instagram Login tokens expire after 60 days: renew them before then (the token must be at least 24h old). The new token is written straight to your settings file, never printed:

```bash
uv run instagram-mcp refresh-token
```

## Configuration

| Variable | Default | |
|---|---|---|
| `IG_LOGIN` | `instagram` | `facebook` (unified login or Page token) or `instagram` (Instagram Login) |
| `IG_ACCESS_TOKEN` | — | Required |
| `IG_USER_ID` | `me` | Numeric Instagram account ID with `facebook`, `me` with `instagram` |
| `IG_API_VERSION` | `v26.0` | Graph API version |
| `IG_DB_PATH` | `instagram_history.db` | SQLite history file, relative to the settings file |
| `IG_ENV_FILE` | `~/.instagram-mcp/.env` | Where settings are read (set as an environment variable) |

Meta renames metrics regularly (e.g. `impressions` → `views` in 2025). Metric lists live in [`src/instagram_mcp/metrics.py`](src/instagram_mcp/metrics.py); unsupported metrics are skipped automatically instead of breaking the call.

## Limitations

- Audience demographics need at least 100 followers.
- Account insights cover at most 30 days per request (history beyond that comes from snapshots).
- Competitor accounts: insights are private; only public counters are available via Business Discovery (not implemented yet).

## Development

```bash
uv run pytest
```

Tests use a fake Instagram API, so no token is needed.

## License

MIT
