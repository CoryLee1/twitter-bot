from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import re

import requests

from env_utils import env_bool, env_list
from free_trend_sources import get_free_web_trend_hints
from http_utils import raise_for_status


CHROME_WEB_STORE_URL = (
    "https://chromewebstore.google.com/detail/"
    "tabii-your-tab-saving-bud/ldlifbcdlbonphobedkmignnjmfjdemk"
)
WEBSITE_URL = "https://www.tabiiclean.com/"
X_TRENDS_URL = "https://api.x.com/2/trends/by/woeid/{woeid}"
X_RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"

DEFAULT_TOPICS = [
    "too many browser tabs",
    "I'll read this later",
    "research rabbit hole",
    "ADHD browser chaos",
    "designer inspiration hoarding",
    "student research panic",
    "AI workflow but messy browser",
    "Chrome eating memory",
]

DEFAULT_TREND_KEYWORDS = [
    "AI workflow",
    "deadline panic",
    "study setup",
    "designer problems",
    "procrastination",
    "Chrome tabs",
    "research rabbit hole",
    "too many tabs",
]

PRODUCT_HASHTAGS = [
    "#Productivity",
    "#ChromeExtension",
    "#BrowserExtension",
    "#TabManagement",
    "#DesignTools",
    "#StudyTools",
]

MEME_BRIDGES = [
    "too many tabs",
    "I will read this later",
    "research rabbit hole",
    "ADHD browser chaos",
    "designer inspiration hoarding",
    "student paper panic",
    "AI workflow with a messy browser",
    "Chrome memory chaos",
]

BLOCKED_TREND_WORDS = [
    "war",
    "death",
    "shooting",
    "earthquake",
    "attack",
    "lawsuit",
    "scandal",
    "election",
]


@dataclass
class TweetPlan:
    topic: str
    trend: str | None
    angle: str
    hashtags: list[str]
    cta_mode: str
    cta_url: str | None
    reply_text: str | None
    trend_snapshot: str = ""
    trend_search_snippets: str = ""


@dataclass
class GeneratedTweet:
    text: str
    plan: TweetPlan
    score: int
    rationale: str
    media_path: str | None = None


def get_topics() -> list[str]:
    return env_list("TWEET_TOPICS", DEFAULT_TOPICS)


def get_manual_trends() -> list[str]:
    return env_list("TREND_KEYWORDS", DEFAULT_TREND_KEYWORDS)


def fetch_x_trends() -> list[str]:
    bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        return []

    woeid = os.getenv("X_TRENDS_WOEID", "1")
    response = requests.get(
        X_TRENDS_URL.format(woeid=woeid),
        headers={"Authorization": f"Bearer {bearer_token}"},
        timeout=30,
    )
    raise_for_status(response, "X trends")
    data = response.json()
    trends = data.get("data", [])
    return [trend["trend_name"] for trend in trends if trend.get("trend_name")]


def get_live_trends() -> list[str]:
    """
    Official X trends for the configured WOEID (requires app Bearer + API access).
    These are fresher than static TREND_KEYWORDS and are listed first when merged.
    """
    if not env_bool("ENABLE_X_TRENDS", False):
        return []
    if not os.getenv("TWITTER_BEARER_TOKEN"):
        return []
    try:
        return fetch_x_trends()
    except Exception as error:
        print(f"Skipping X trends: {error}")
        return []


def get_candidate_trends() -> list[str]:
    """Live X trends first (deduped), then manual ``TREND_KEYWORDS``."""
    seen: set[str] = set()
    merged: list[str] = []
    for trend in get_live_trends() + get_manual_trends():
        key = trend.strip().lower()
        if not key or key in seen or not is_safe_trend(trend):
            continue
        seen.add(key)
        merged.append(trend.strip())
    return merged


def trend_snapshot_top_n() -> int:
    raw = os.getenv("TREND_SNAPSHOT_TOP_N", "12")
    try:
        return max(3, min(30, int(raw)))
    except ValueError:
        return 12


def format_trend_snapshot(trends: list[str], top_n: int) -> str:
    if not trends:
        return (
            "(No trend list — write something that still feels like today's X: "
            "specific, slice-of-internet, not generic productivity advice.)"
        )
    lines = trends[:top_n]
    return "\n".join(f"- {name}" for name in lines)


def trend_to_search_query(trend: str) -> str:
    text = re.sub(r"#[^\s#]+", " ", trend)
    text = re.sub(r"[@]", " ", text)
    text = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return " ".join(text.split()[:6])


def fetch_trend_recent_search_snippets(trend: str) -> str:
    """
    Pull a few *recent public posts* for the trending phrase to ground copy in real vibe.
    Requires ``TWITTER_BEARER_TOKEN`` with Recent Search access (not all tiers include it).
    """
    if not env_bool("ENABLE_TREND_RECENT_SEARCH", False):
        return ""
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if not bearer:
        return ""

    query = trend_to_search_query(trend)
    if len(query) < 2:
        return ""

    try:
        response = requests.get(
            X_RECENT_SEARCH_URL,
            headers={"Authorization": f"Bearer {bearer}"},
            params={
                "query": query,
                "max_results": 10,
                "tweet.fields": "text",
            },
            timeout=25,
        )
        if response.status_code != 200:
            print(f"Trend recent search HTTP {response.status_code} (trend context skipped).")
            return ""
        payload = response.json()
    except (requests.RequestException, OSError) as error:
        print(f"Trend recent search skipped: {error}")
        return ""

    tweets = payload.get("data") or []
    texts = [
        str(row.get("text", "")).replace("\n", " ").strip()
        for row in tweets
        if row.get("text")
    ]
    texts = [row for row in texts if row]
    if not texts:
        return ""

    merged = "\n".join(texts[:6])
    if len(merged) > 900:
        merged = merged[:900].rstrip() + "…"
    return (
        "Recent public post *paraphrase fuel* (do NOT quote verbatim; avoid @handles; "
        "capture tone/meme only):\n"
        f"{merged}"
    )


def append_free_web_hint_block(snapshot: str) -> str:
    hints = get_free_web_trend_hints()
    if not hints:
        return snapshot
    lines = "\n".join(f"- {h}" for h in hints[:16])
    return (
        f"{snapshot}\n"
        f"\n---\n"
        f"Open-web pulse (Reddit/HN headlines — not official X trends; vibe only, "
        f"do not paste subreddit names awkwardly):\n"
        f"{lines}"
    )


def compose_hook_planning() -> tuple[str, str | None, str, str, str]:
    """Single fetch of trend pool per tweet; aligns topic/angle to chosen trend."""
    trends = get_candidate_trends()
    topics = get_topics()
    trend = choose_weighted_trend(trends)
    topic = pick_topic_for_trend(trend, topics)
    angle = pick_angle_for_trend(trend)
    snapshot = format_trend_snapshot(trends, trend_snapshot_top_n())
    snapshot = append_free_web_hint_block(snapshot)
    snippets = fetch_trend_recent_search_snippets(trend) if trend else ""
    return topic, trend, angle, snapshot, snippets


def choose_weighted_trend(trends: list[str]) -> str | None:
    """Prefer earlier items (official trends are merged first)."""
    if not trends:
        return None
    size = len(trends)
    weights = [max(1, size - index) for index in range(size)]
    return random.choices(trends, weights=weights, k=1)[0]


def pick_topic_for_trend(trend: str | None, topics: list[str]) -> str:
    if not trend or not topics:
        return random.choice(topics)

    tl = re.sub(r"#[^\s#]+", "", trend).lower()
    tl = re.sub(r"\s+", " ", tl).strip()
    trend_tokens = {w for w in re.findall(r"[a-z]{3,}", tl)}

    best_topic = None
    best_score = 0
    for topic in topics:
        topic_tokens = set(re.findall(r"[a-z]{3,}", topic.lower()))
        score = len(trend_tokens & topic_tokens)
        if score > best_score:
            best_score = score
            best_topic = topic
    if best_topic is not None and best_score > 0:
        return best_topic

    tl_full = tl
    if any(k in tl_full for k in ("ai", "gpt", "openai", "claude", "gemini", "llm", "copilot")):
        for topic in topics:
            lower = topic.lower()
            if "ai" in lower or "workflow" in lower:
                return topic
    if any(k in tl_full for k in ("design", "figma", "ui ", "ux ", "creative")):
        for topic in topics:
            if "design" in topic.lower():
                return topic
    if any(
        k in tl_full
        for k in ("study", "exam", "student", "college", "uni", "school", "midterm", "finals")
    ):
        for topic in topics:
            lower = topic.lower()
            if "student" in lower or "study" in lower or "research" in lower:
                return topic
    return random.choice(topics)


def pick_angle_for_trend(trend: str | None) -> str:
    if not trend:
        return random.choice(MEME_BRIDGES)

    tl = trend.lower()
    if any(k in tl for k in ("ai", "gpt", "openai", "claude", "gemini", "llm", "copilot")):
        return "AI workflow with a messy browser"
    if any(k in tl for k in ("design", "figma", "ui", "ux", "pixel", "font")):
        return "designer inspiration hoarding"
    if any(
        k in tl
        for k in (
            "study",
            "exam",
            "student",
            "college",
            "school",
            "homework",
            "midterm",
            "finals",
        )
    ):
        return "student research panic"
    if any(k in tl for k in ("chrome", "safari", "firefox", "browser", "tab")):
        return "Chrome memory chaos"
    return random.choice(MEME_BRIDGES)


def is_safe_trend(trend: str) -> bool:
    lower = trend.lower()
    return not any(word in lower for word in BLOCKED_TREND_WORDS)


def normalize_hashtag(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    explicit = re.search(r"#[A-Za-z][A-Za-z0-9_]{2,40}", text)
    if explicit:
        return explicit.group(0)

    words = re.findall(r"[A-Za-z][A-Za-z0-9]{1,20}", text)
    if not words:
        return None

    tag = "#" + "".join(word[:1].upper() + word[1:] for word in words[:3])
    return tag if 3 <= len(tag) <= 40 else None


def choose_hashtags(trend: str | None, topic: str) -> list[str]:
    tags: list[str] = []

    trend_tag = normalize_hashtag(trend or "")
    if trend_tag and is_safe_trend(trend_tag):
        tags.append(trend_tag)

    lower_topic = topic.lower()
    if "design" in lower_topic:
        product_tag = "#DesignTools"
    elif "student" in lower_topic or "study" in lower_topic or "research" in lower_topic:
        product_tag = "#StudyTools"
    elif "tab" in lower_topic:
        product_tag = "#TabManagement"
    else:
        product_tag = random.choice(PRODUCT_HASHTAGS)

    if product_tag not in tags:
        tags.append(product_tag)

    if len(tags) == 1:
        fallback = "#ChromeExtension"
        if fallback not in tags:
            tags.append(fallback)

    return tags[:2]


def choose_cta_mode() -> tuple[str, str | None, str | None]:
    cta_mode = random.choices(
        ["reply_install", "direct_install", "website", "none"],
        weights=[60, 20, 10, 10],
        k=1,
    )[0]

    if cta_mode == "reply_install":
        return (
            cta_mode,
            CHROME_WEB_STORE_URL,
            f"Try Tabii on Chrome Web Store: {CHROME_WEB_STORE_URL}",
        )
    if cta_mode == "direct_install":
        return cta_mode, CHROME_WEB_STORE_URL, None
    if cta_mode == "website":
        return cta_mode, WEBSITE_URL, None
    return cta_mode, None, None


def choose_cta_mode_image_post() -> tuple[str, str | None, str | None]:
    """Softer CTAs for image-first posts (virality over conversion)."""
    cta_mode = random.choices(
        ["none", "reply_install", "direct_install", "website"],
        weights=[72, 18, 6, 4],
        k=1,
    )[0]
    if cta_mode == "reply_install":
        return (
            cta_mode,
            CHROME_WEB_STORE_URL,
            f"Try Tabii on Chrome Web Store: {CHROME_WEB_STORE_URL}",
        )
    if cta_mode == "direct_install":
        return cta_mode, CHROME_WEB_STORE_URL, None
    if cta_mode == "website":
        return cta_mode, WEBSITE_URL, None
    return cta_mode, None, None


def choose_hashtags_image_post(trend: str | None, topic: str) -> list[str]:
    """Trend-leaning tags; avoid hard-selling product tags."""
    tags: list[str] = []
    trend_tag = normalize_hashtag(trend or "")
    if trend_tag and is_safe_trend(trend_tag):
        tags.append(trend_tag)

    topic_tag = normalize_hashtag(topic)
    if topic_tag and topic_tag not in tags and is_safe_trend(topic_tag):
        if len(topic_tag) <= 22:
            tags.append(topic_tag)

    if not tags:
        tags.append("#TechTwitter")
    return tags[:2]


def build_image_tweet_plan() -> TweetPlan:
    topic, trend, angle, snap, snippets = compose_hook_planning()
    cta_mode, cta_url, reply_text = choose_cta_mode_image_post()
    return TweetPlan(
        topic=topic,
        trend=trend,
        angle=angle,
        hashtags=choose_hashtags_image_post(trend, topic),
        cta_mode=cta_mode,
        cta_url=cta_url,
        reply_text=reply_text,
        trend_snapshot=snap,
        trend_search_snippets=snippets,
    )


def build_image_generation_prompt(plan: TweetPlan) -> str:
    trend_line = plan.trend or "no specific live trend token"
    cta_instruction = (
        f"If it fits naturally, mention or link once: {plan.cta_url}."
        if plan.cta_mode in {"direct_install", "website"} and plan.cta_url
        else "Do not put any URL in the main tweet."
    )
    hashtags = " ".join(plan.hashtags)
    return f"""
You caption a viral X/Twitter post that includes an attached image (you can see it).

The post should feel like native Twitter: sharp, funny, slightly provocative or debatable,
but not cruel, hateful, harassing, or misleading. It is fine if the post does NOT mention
any product or brand. You may only lightly nod to browser tabs, digital hoarding, ADHD,
design, study, or productivity if it matches the image + trend.

Hook ideas: tie the *visual* in the image to what people are arguing about online today
because of this trend hook: "{trend_line}".
Topic seed (optional): {plan.topic}
Angle seed (optional): {plan.angle}

Trending snapshot (names only; you may deviate if the chosen hook is stronger):
{plan.trend_snapshot}
{f"Optional real-vibe hints:\\n{plan.trend_search_snippets}" if plan.trend_search_snippets else ""}

Hard requirement: a reader scrolling the For You feed must sense this belongs to *today's*
public conversation (newsjacking / meme lane), not evergreen marketing.

Avoid tragedy, politics, disasters, medical claims, scams, and engagement farming:
no "like if…", "repost if…", RT/Follow beg, "signal boost", "blow this up", "tag someone who…".
Use exactly the required hashtags (1–2 total): {hashtags}
{cta_instruction}
English only. Max 280 characters per tweet.

Return JSON only:
{{
  "candidates": [
    {{
      "text": "tweet text",
      "score": 1,
      "rationale": "short reason"
    }}
  ]
}}
Write exactly 3 candidates with distinct angles; score 1–10 by predicted reply/quote potential.
""".strip()


def build_tweet_plan() -> TweetPlan:
    topic, trend, angle, snap, snippets = compose_hook_planning()
    cta_mode, cta_url, reply_text = choose_cta_mode()
    return TweetPlan(
        topic=topic,
        trend=trend,
        angle=angle,
        hashtags=choose_hashtags(trend, topic),
        cta_mode=cta_mode,
        cta_url=cta_url,
        reply_text=reply_text,
        trend_snapshot=snap,
        trend_search_snippets=snippets,
    )


def product_context() -> str:
    return """
Tabii is a Chrome extension for tab hoarders.
Core product:
- Leo, a tiny elephant browser companion.
- One click turns messy open tabs into visual saved cards.
- Saved pages become a searchable visual board, like an inspiration wall.
- Users can search by memory, not just exact titles or URLs.
- Useful for designers, students, researchers, ADHD users, and anyone with too many tabs.
- Local-first and privacy-friendly.
Primary conversion URL: Chrome Web Store.
Secondary brand URL: tabiiclean.com.
""".strip()


def build_generation_prompt(plan: TweetPlan) -> str:
    trend_line = plan.trend or "no live trend available"
    cta_instruction = (
        f"If natural, include this URL once: {plan.cta_url}."
        if plan.cta_mode in {"direct_install", "website"} and plan.cta_url
        else "Do not include a URL in the main tweet."
    )
    hashtags = " ".join(plan.hashtags)
    return f"""
You write high-performing X/Twitter posts for @TabiiClean.

Product context:
{product_context()}

Current topic: {plan.topic}
Primary trend/meme lane to ride (your main hook): {trend_line}
Bridge angle: {plan.angle}
Required hashtags: {hashtags}

Trending snapshot (prefer staying inside this cultural weather; names only):
{plan.trend_snapshot}
{f"Optional live-vibe hints (paraphrase only, never quote):\\n{plan.trend_search_snippets}" if plan.trend_search_snippets else ""}

Write 3 candidate tweets that feel native to X: funny, relatable, slightly playful, not corporate.
Ground at least one specific cue (language, grievance, or joke format) in the primary trend lane
or the snapshot so it does not read like generic productivity spam.
It is okay to use meme language if it naturally connects back to tab chaos, browser clutter, research rabbit holes, or Leo the elephant.

Avoid tragedy, politics, disasters, spam, fake claims, and engagement farming:
no "like if…", "repost if…", RT/Follow beg, "signal boost", "blow this up",
"tag someone who", or other explicit calls for engagement.
Use 1-2 hashtags total, exactly from the required hashtags list.
{cta_instruction}
Keep each tweet under 280 characters.

Return JSON only in this shape:
{{
  "candidates": [
    {{
      "text": "tweet text",
      "score": 1,
      "rationale": "short reason"
    }}
  ]
}}
""".strip()


def parse_candidates(raw_text: str, plan: TweetPlan) -> list[GeneratedTweet]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    data = json.loads(cleaned)
    candidates = data.get("candidates", [])
    generated: list[GeneratedTweet] = []
    for candidate in candidates:
        text = str(candidate.get("text", "")).strip()
        if not text:
            continue
        generated.append(
            GeneratedTweet(
                text=format_tweet_text(text, plan),
                plan=plan,
                score=int(candidate.get("score", 0)),
                rationale=str(candidate.get("rationale", "")).strip(),
            )
        )
    return generated


def remove_hashtags(text: str) -> str:
    return re.sub(r"\s*#[A-Za-z][A-Za-z0-9_]*", "", text).strip()


def remove_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text).strip()


def clean_tweet_text(text: str) -> str:
    tweet = text.strip().strip('"')
    if len(tweet) > 280:
        tweet = tweet[:280].rstrip()
    return tweet


def trim_body_for_suffix(body: str, suffix: str) -> str:
    max_body_length = 280 - len(suffix) - (1 if suffix else 0)
    body = body.strip()
    if len(body) <= max_body_length:
        return body

    truncated = body[:max_body_length].rstrip()
    sentence_end = max(
        truncated.rfind("."),
        truncated.rfind("!"),
        truncated.rfind("?"),
    )
    if sentence_end >= 80:
        return truncated[: sentence_end + 1].strip()

    word_end = truncated.rfind(" ")
    if word_end >= 80:
        return truncated[:word_end].strip()

    return truncated


def format_tweet_text(text: str, plan: TweetPlan) -> str:
    tweet = remove_hashtags(text)
    tweet = remove_urls(tweet)

    suffix_parts = plan.hashtags[:2]
    if plan.cta_mode in {"direct_install", "website"} and plan.cta_url:
        suffix_parts.append(plan.cta_url)

    suffix = " ".join(suffix_parts)
    tweet = trim_body_for_suffix(tweet, suffix)
    if suffix:
        tweet = f"{tweet} {suffix}"

    return clean_tweet_text(tweet)


def fallback_tweet(plan: TweetPlan) -> GeneratedTweet:
    hashtags = " ".join(plan.hashtags)
    text = (
        f"My toxic trait is keeping 47 tabs open because each one represents "
        f"a different version of who I might become. {hashtags}"
    )
    if plan.cta_mode in {"direct_install", "website"} and plan.cta_url:
        text = f"{text}\n{plan.cta_url}"
    return GeneratedTweet(
        text=format_tweet_text(text, plan),
        plan=plan,
        score=1,
        rationale="Fallback meme template.",
    )


def choose_best_candidate(candidates: list[GeneratedTweet], plan: TweetPlan) -> GeneratedTweet:
    valid = [candidate for candidate in candidates if len(candidate.text) <= 280]
    if not valid:
        return fallback_tweet(plan)
    return max(valid, key=lambda candidate: candidate.score)
