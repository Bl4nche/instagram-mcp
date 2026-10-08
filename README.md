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

## Requirements

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- An Instagram **Business or Creator** account (personal profiles are not supported by the API)
- A Meta developer app (free, see below)

## 1. Create the Meta app and get a token

1. Go to [developers.facebook.com](https://developers.facebook.com/apps) → **Create app**.
2. Choose the use case **Manage messaging & content on Instagram** (Instagram API with Instagram Login). No Facebook Page needed.
3. In **API setup with Instagram login**, under *Generate access tokens*, click **Add account** and log in with your Instagram account.
4. Make sure the permissions include `instagram_business_basic` and `instagram_business_manage_insights`.
5. Click **Generate token** and copy it. It is a long-lived token, valid for **60 days**.

While the app is in **development mode** it works for any Instagram account that has a role on the app (yours, or accounts added as Instagram testers). **App Review is only required** if you want other people to connect their accounts through your app.

## 2. Install

```bash
git clone https://github.com/<your-username>/instagram-mcp.git
cd instagram-mcp
cp .env.example .env      # then paste the token into IG_ACCESS_TOKEN
uv sync
```

Quick check:

```bash
uv run instagram-mcp snapshot
```

## 3. Connect it to Claude

**Claude Code**

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

Long-lived tokens expire after 60 days. Renew before then (the token must be at least 24h old):

```bash
uv run instagram-mcp refresh-token
```

Paste the new token into `.env`.

## Configuration

| Variable | Default | |
|---|---|---|
| `IG_ACCESS_TOKEN` | — | Required |
| `IG_USER_ID` | `me` | Instagram user ID, `me` = token owner |
| `IG_API_VERSION` | `v23.0` | Graph API version |
| `IG_DB_PATH` | `instagram_history.db` | SQLite history file |

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
