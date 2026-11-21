---
name: insights-for-instagram
description: Analyzes the organic performance of an Instagram Business or Creator account (posts, reels, carousels, stories, reach, followers, audience) using the read-only tools of the instagram-mcp server and its local snapshot history. Use it when the user asks how their Instagram content is doing, which posts or reels performed best, how followers are growing, how past stories did, who their audience is, or wants to save a snapshot or check that their Instagram connection works.
argument-hint: [question or period, e.g. "best reels this month"]
---

# Insights for Instagram

Request: `$ARGUMENTS`

The data comes from the tools of the `instagram` MCP server ([instagram-mcp](https://github.com/Bl4nche/instagram-mcp)). The server **only reads**: it never posts, comments, sends messages or changes anything on the account. Do not offer actions that would need that.

Always reply in the user's language, and format dates and numbers the way their locale does.

## 1. Check the connection

Always call `get_profile` first and state which account you are working on (username and follower count). Repeat the analyzed account in the final answer. Every user connects their own account: never assume which one it is.

If it fails:

| Error | What to tell the user |
|---|---|
| `instagram` tools not available | The MCP server is not installed or not running: see "Setup" below. |
| `IG_ACCESS_TOKEN is not set` | The account is not connected yet: the user runs `instagram-mcp setup` in their own terminal (see "Setup"). |
| `numeric Instagram account ID` | The account ID is missing: run `setup` again and enter the number that starts with 1784. |
| Code 190 / expired token | Instagram Login tokens last 60 days: `instagram-mcp refresh-token`. Other tokens do not expire: if one stops working it was revoked, so generate a new one and run `setup` again. |
| Code 10 / 200 / permissions | The token lacks the insights permission (`instagram_manage_insights` or `instagram_business_manage_insights`): see the server's README, section 1. |

## 2. Pick the tools

| Question | Tool |
|---|---|
| Latest posts and reels | `list_media` |
| One piece of content in detail | `get_media_insights` (with the `id` from `list_media`) |
| Best / worst content | `top_posts` with `by` = `er_reach_pct`, `er_followers_pct`, `reach`, `views`, `saved`, `shares`… |
| Account totals (max 30 days) | `get_account_insights` |
| Audience | `get_audience` with `breakdown` = `age`, `gender`, `city` or `country` (needs at least 100 followers) |
| Stories from the last 24 hours | `get_active_stories` |
| Older stories | `story_archive` (only those saved by snapshots) |
| Follower growth over time | `follower_history` |
| How a post's numbers grew | `media_metric_history` |
| Save the current state | `snapshot` |

`top_posts` and `get_media_insights` make one API call per item: keep `limit` around 25 unless more is needed. To compare one format (reels, carousels), fetch with `top_posts` and filter by `media_product_type` (`REELS`, `FEED`) and `media_type` (`VIDEO`, `CAROUSEL_ALBUM`, `IMAGE`); filter by `timestamp` for a period.

## 3. Read the numbers honestly

- **Engagement rate**: `er_reach_pct` = interactions / reach (how engaging the content was for those who saw it); `er_followers_pct` = interactions / followers (the usual industry benchmark). Always say which one you use.
- `ig_reels_avg_watch_time` is in **milliseconds**: convert to seconds.
- `views` counts repeated views (and swipes through carousel slides), so it can exceed reach.
- The API gives no totals beyond 30 days: use the local history and say when it starts (first snapshot). If the history is empty, say so and suggest scheduling snapshots (server README, section 4) instead of estimating.
- Instagram deletes story insights after 24 hours: anything not in `story_archive` cannot be recovered.
- Meta renames metrics (`impressions` → `views` in 2025): a missing metric was skipped, it is not zero.
- Compare like with like (reels with reels, carousels with carousels) and point out when the sample is small.
- Do not invent causes the data does not show.

## 4. Answer

Open with the answer in 2-3 lines, then a table with the numbers (content linked with its `permalink`, date, metrics), and close with at most three practical observations.

## Privacy

- **Never ask for the token in chat**, and never read, print or edit the server's `.env` file. Do not run `setup` yourself (it asks for the token): the user runs it in their own terminal. To check the connection use `get_profile` or `instagram-mcp check`, which never show the token.
- If the user pastes a token in chat by mistake, tell them to revoke it and generate a new one.
- Settings and history stay on the user's computer (`~/.instagram-mcp/`); the server only talks to Meta.

## Setup (if the connection is missing)

1. Install [uv](https://docs.astral.sh/uv/) and get the server: `git clone https://github.com/Bl4nche/instagram-mcp` then `uv sync` in that folder.
2. Create your own Meta app and token by following the server's README, section 1. Each person uses their own app and account; with new Meta apps (unified login) the token never expires.
3. In your own terminal, from the server folder: `uv run instagram-mcp setup`. It asks for the login type, account ID and token (hidden input), checks them with Meta and saves them to `~/.instagram-mcp/.env`, private and outside the code folder. The history is saved there too.
4. Add the server to your AI client (Claude Code plugin, Claude Desktop or any MCP client: README, section 3), restart it and check with `get_profile`.

The server works on **one account at a time**: run `setup` again to switch.
