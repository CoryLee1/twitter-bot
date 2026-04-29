# Tabii Twitter Bot

Small Python bot that generates short tweets for `@TabiiClean` with zero-cost templates, Doubao/Ark, local Ollama, or OpenAI, then posts them through the X API.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your preferred auth mode.

OAuth 2.0 user context:

- `TWITTER_AUTH_MODE=oauth2`
- `TWITTER_CLIENT_ID`
- `TWITTER_CLIENT_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_REFRESH_TOKEN`
- `LLM_PROVIDER=template`

OAuth 1.0a alternative:

- `TWITTER_AUTH_MODE=oauth1`
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_TOKEN_SECRET`
- `LLM_PROVIDER=template`

For OAuth 2.0, the token needs user-context scopes including `tweet.write`, `tweet.read`, `users.read`, and `offline.access`. The script refreshes the access token before posting and writes rotated tokens back to `.env`.

## Zero-Cost Mode

If you do not want any paid AI API, use template mode:

```bash
LLM_PROVIDER=template
```

This uses hand-written Tabii/X meme templates, then still applies the same topic, trend keyword, hashtag, and CTA strategy. It works well for cheap VPS, cron, or GitHub Actions because it does not need OpenAI or Ollama.

## Doubao / Ark

Doubao is supported through Volcengine Ark's Responses API:

```bash
LLM_PROVIDER=doubao
ARK_API_KEY=your_ark_api_key
ARK_MODEL=doubao-seed-2-0-pro-260215
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/responses
```

The bot prompt asks for native English X/Twitter posts, so Doubao will generate English tweet candidates.

## Local Llama With Ollama

Install Ollama, then pull a model:

```bash
ollama pull llama3.1:8b
```

Use this in `.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

For a lighter model:

```bash
ollama pull llama3.2:3b
OLLAMA_MODEL=llama3.2:3b
```

OpenAI is still supported if you set:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

## Free GitHub Actions Deployment

The repo includes `.github/workflows/post-tweet.yml`, which runs three times a day using GitHub's scheduled workflows and `LLM_PROVIDER=template`.

For GitHub Actions, OAuth 1.0a is recommended because those tokens do not rotate. Add these repository secrets in GitHub:

- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_TOKEN_SECRET`

Then the workflow will run automatically at UTC times equivalent to `00:30`, `08:30`, and `21:30` in UTC+8.

OAuth 2.0 is better for a VPS or local always-on machine, because refresh tokens may rotate and the updated `.env` needs to persist between runs.

## Render Deployment

The repo includes `render.yaml` for a Render Background Worker. It runs:

```bash
python post_tweet.py
```

This keeps the bot process alive and lets the internal scheduler post at:

```bash
POST_TIMES=00:30,08:30,21:30
```

The Render Blueprint asks you to fill these secret values in the dashboard:

- `TWITTER_CLIENT_ID`
- `TWITTER_CLIENT_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_REFRESH_TOKEN`
- `ARK_API_KEY`

The default Render config uses:

```bash
TWITTER_AUTH_MODE=oauth2
LLM_PROVIDER=doubao
```

Note: OAuth 2.0 refresh tokens can rotate. A long-running Render worker is acceptable, but a restart may require updating `TWITTER_REFRESH_TOKEN` in Render if X invalidates the old token. OAuth 1.0a is still the most stable choice for stateless cron-style deployments.

## Run Once

Useful for testing or cron:

```bash
python post_tweet.py --once
```

## Preview Before Posting

Generate the tweet plan without posting to X:

```bash
python post_tweet.py --dry-run
```

The preview prints:

- main tweet text
- optional first reply with the install link
- selected topic/trend angle
- hashtags
- CTA mode
- LLM score/rationale

## Content Strategy

The bot is tuned for Tabii's positioning:

- Leo, a tiny elephant browser companion
- one-click cleanup for messy tabs
- visual saved-card board
- search by memory, not exact titles
- local-first privacy
- Chrome Web Store as the main conversion target

Edit these comma-separated lists in `.env` to control the content without changing code:

```bash
TWEET_TOPICS=too many browser tabs,I'll read this later,research rabbit hole,ADHD browser chaos
TREND_KEYWORDS=AI workflow,deadline panic,study setup,designer problems,Chrome tabs
```

The generator uses 1-2 hashtags per tweet. It defaults to one product/audience tag such as `#ChromeExtension` or `#TabManagement`, plus one trend tag only when it fits naturally.

CTA behavior is intentionally mixed:

- most posts keep the main tweet link-free and put the Chrome Web Store link in the first reply
- some posts include the Chrome Web Store link directly
- a small number link to the website for brand explanation

Optional official X Trends can be enabled if your API tier supports it:

```bash
ENABLE_X_TRENDS=true
TWITTER_BEARER_TOKEN=your_app_bearer_token
X_TRENDS_WOEID=1
```

## Run Scheduler

By default it posts three times a day in your machine's local timezone. For a UTC+8 machine, this schedule is tuned to hit US X traffic peaks:

- `00:30` UTC+8: US midday/morning
- `08:30` UTC+8: US evening
- `21:30` UTC+8: US morning

```bash
python post_tweet.py
```

Customize the schedule and topics in `.env`:

```bash
POST_TIMES=00:30,08:30,21:30
TWEET_TOPICS=bookmark organization tip,tab management productivity,visual bookmarking workflow
```

## Cron Example

```cron
30 0,8,21 * * * cd /path/to/Tabii-twitterbot && /path/to/Tabii-twitterbot/.venv/bin/python post_tweet.py --once
```
