"""Free trend-adjacent hints without paid X trend APIs (Reddit, Hacker News).

These are *inspiration strings* for the LLM, not official X trending hashtags.
Respect each site's rate limits; keep volume low (a few requests per bot run).
"""

from __future__ import annotations

import os

import requests

from env_utils import env_bool, env_list

REDDIT_HOT_URL = "https://www.reddit.com/r/{subreddit}/hot.json"
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


def _truncate_phrase(text: str, max_len: int = 96) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def fetch_reddit_hot_phrases() -> list[str]:
    """
    Public ``.json`` endpoints — no OAuth. Reddit expects a descriptive User-Agent.
    """
    if not env_bool("ENABLE_REDDIT_TREND_HINTS", False):
        return []

    subs = env_list(
        "REDDIT_TREND_SUBREDDITS",
        ["technology", "webdev", "productivity", "internetIsBeautiful"],
    )
    user_agent = os.getenv(
        "REDDIT_USER_AGENT",
        "TabiiCleanTwitterBot/1.0 (productivity Chrome extension; +https://www.tabiiclean.com/)",
    )
    titles_per_sub = 4
    out: list[str] = []

    for raw in subs[:5]:
        sub = raw.strip().strip("/").removeprefix("r/").strip()
        if not sub:
            continue
        try:
            response = requests.get(
                REDDIT_HOT_URL.format(subreddit=sub),
                headers={"User-Agent": user_agent},
                params={"limit": 15},
                timeout=18,
            )
            if response.status_code != 200:
                print(f"Reddit r/{sub} hints skipped: HTTP {response.status_code}")
                continue
            payload = response.json()
        except (requests.RequestException, ValueError, OSError) as error:
            print(f"Reddit r/{sub} hints skipped: {error}")
            continue

        count = 0
        for child in payload.get("data", {}).get("children", []):
            data = child.get("data") or {}
            if data.get("stickied"):
                continue
            title = str(data.get("title", "")).strip()
            if not title:
                continue
            out.append(f"r/{sub}: {_truncate_phrase(title)}")
            count += 1
            if count >= titles_per_sub:
                break

    return out


def fetch_hn_hot_phrases() -> list[str]:
    """Hacker News front-page titles via official read-only Firebase API."""
    if not env_bool("ENABLE_HN_TREND_HINTS", False):
        return []

    max_titles = 8
    out: list[str] = []
    try:
        listing = requests.get(HN_TOP_URL, timeout=12)
        if listing.status_code != 200:
            print(f"Hacker News hints skipped: HTTP {listing.status_code}")
            return []
        id_list = listing.json()
        if not isinstance(id_list, list):
            return []
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"Hacker News hints skipped: {error}")
        return []

    for item_id in id_list[:20]:
        if len(out) >= max_titles:
            break
        try:
            row = requests.get(
                HN_ITEM_URL.format(item_id=item_id),
                timeout=12,
            )
            if row.status_code != 200:
                continue
            data = row.json()
        except (requests.RequestException, ValueError, OSError):
            continue
        title = str(data.get("title", "")).strip()
        if title:
            out.append(f"HN: {_truncate_phrase(title)}")

    return out


def get_free_web_trend_hints() -> list[str]:
    """Aggregated cheap hints; merged into ``TREND_KEYWORDS`` pool in content_strategy."""
    return fetch_reddit_hot_phrases() + fetch_hn_hot_phrases()
