from __future__ import annotations

from dataclasses import dataclass
import json
import os
import random
import re

import requests

from env_utils import env_bool, env_list
from http_utils import raise_for_status


CHROME_WEB_STORE_URL = (
    "https://chromewebstore.google.com/detail/"
    "tabii-your-tab-saving-bud/ldlifbcdlbonphobedkmignnjmfjdemk"
)
WEBSITE_URL = "https://www.tabiiclean.com/"
X_TRENDS_URL = "https://api.x.com/2/trends/by/woeid/{woeid}"

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


@dataclass
class GeneratedTweet:
    text: str
    plan: TweetPlan
    score: int
    rationale: str


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


def get_candidate_trends() -> list[str]:
    trends: list[str] = []
    if env_bool("ENABLE_X_TRENDS", False):
        try:
            trends.extend(fetch_x_trends())
        except Exception as error:
            print(f"Skipping X trends: {error}")

    trends.extend(get_manual_trends())
    deduped = list(dict.fromkeys(trends))
    return [trend for trend in deduped if is_safe_trend(trend)]


def is_safe_trend(trend: str) -> bool:
    lower = trend.lower()
    return not any(word in lower for word in BLOCKED_TREND_WORDS)


def choose_topic_and_trend() -> tuple[str, str | None, str]:
    topics = get_topics()
    trends = get_candidate_trends()
    topic = random.choice(topics)
    trend = random.choice(trends) if trends else None
    angle = random.choice(MEME_BRIDGES)
    return topic, trend, angle


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


def build_tweet_plan() -> TweetPlan:
    topic, trend, angle = choose_topic_and_trend()
    cta_mode, cta_url, reply_text = choose_cta_mode()
    return TweetPlan(
        topic=topic,
        trend=trend,
        angle=angle,
        hashtags=choose_hashtags(trend, topic),
        cta_mode=cta_mode,
        cta_url=cta_url,
        reply_text=reply_text,
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
Trend/meme to optionally riff on: {trend_line}
Bridge angle: {plan.angle}
Required hashtags: {hashtags}

Write 3 candidate tweets that feel native to X: funny, relatable, slightly playful, not corporate.
It is okay to use meme language if it naturally connects back to tab chaos, browser clutter, research rabbit holes, or Leo the elephant.
Avoid tragedy, politics, disasters, spam, fake claims, and engagement bait.
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
        tweet = tweet[:277].rstrip() + "..."
    return tweet


def format_tweet_text(text: str, plan: TweetPlan) -> str:
    tweet = remove_hashtags(text)
    tweet = remove_urls(tweet)

    suffix_parts = plan.hashtags[:2]
    if plan.cta_mode in {"direct_install", "website"} and plan.cta_url:
        suffix_parts.append(plan.cta_url)

    suffix = " ".join(suffix_parts)
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
