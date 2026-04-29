# Tabii Twitter Bot

Small Python bot that generates short tweets for `@TabiiClean` with a local Ollama model or OpenAI, then posts them through the X API.

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
- `LLM_PROVIDER=ollama`

OAuth 1.0a alternative:

- `TWITTER_AUTH_MODE=oauth1`
- `TWITTER_API_KEY`
- `TWITTER_API_SECRET`
- `TWITTER_ACCESS_TOKEN`
- `TWITTER_ACCESS_TOKEN_SECRET`
- `LLM_PROVIDER=ollama`

For OAuth 2.0, the token needs user-context scopes including `tweet.write`, `tweet.read`, `users.read`, and `offline.access`. The script refreshes the access token before posting and writes rotated tokens back to `.env`.

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

By default it posts at `09:00`, `14:00`, and `20:00` every day:

```bash
python post_tweet.py
```

Customize the schedule and topics in `.env`:

```bash
POST_TIMES=09:00,14:00,20:00
TWEET_TOPICS=bookmark organization tip,tab management productivity,visual bookmarking workflow
```

## Cron Example

```cron
0 9,14,20 * * * cd /path/to/Tabii-twitterbot && /path/to/Tabii-twitterbot/.venv/bin/python post_tweet.py --once
```
