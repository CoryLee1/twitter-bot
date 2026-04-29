import argparse
import json
import os
import time

import schedule
from dotenv import load_dotenv

from content_strategy import (
    GeneratedTweet,
    build_generation_prompt,
    build_tweet_plan,
    choose_best_candidate,
    fallback_tweet,
    parse_candidates,
)
from env_utils import env_list
from llm_clients import TextGenerator, build_text_generator
from twitter_posters import TwitterPoster, build_twitter_poster


DOTENV_PATH = ".env"


def generate_tweet(generator: TextGenerator) -> GeneratedTweet:
    plan = build_tweet_plan()
    prompt = build_generation_prompt(plan)

    try:
        raw_response = generator.generate(prompt)
        candidates = parse_candidates(raw_response, plan)
    except Exception as error:
        print(f"Falling back to template tweet: {error}")
        return fallback_tweet(plan)

    return choose_best_candidate(candidates, plan)


def print_preview(tweet: GeneratedTweet) -> None:
    plan = tweet.plan
    preview = {
        "tweet": tweet.text,
        "reply": plan.reply_text,
        "topic": plan.topic,
        "trend": plan.trend,
        "angle": plan.angle,
        "hashtags": plan.hashtags,
        "cta_mode": plan.cta_mode,
        "cta_url": plan.cta_url,
        "score": tweet.score,
        "rationale": tweet.rationale,
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))


def post_generated_tweet(twitter_poster: TwitterPoster, tweet: GeneratedTweet) -> str:
    tweet_id = twitter_poster.post(tweet.text)
    print(f"Tweet posted: {tweet_id}")
    print(tweet.text)

    if tweet.plan.reply_text:
        reply_id = twitter_poster.post(tweet.plan.reply_text, reply_to_id=tweet_id)
        print(f"CTA reply posted: {reply_id}")
        print(tweet.plan.reply_text)

    return tweet_id


def run_once(generator: TextGenerator, dry_run: bool) -> None:
    tweet = generate_tweet(generator)
    if dry_run:
        print_preview(tweet)
        return

    twitter_poster = build_twitter_poster()
    post_generated_tweet(twitter_poster, tweet)


def run_scheduler(generator: TextGenerator, dry_run: bool) -> None:
    post_times = env_list("POST_TIMES", ["09:00", "14:00", "20:00"])

    for post_time in post_times:
        schedule.every().day.at(post_time).do(run_once, generator, dry_run)
        print(f"Scheduled daily tweet at {post_time}")

    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and post tweets for @TabiiClean.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Post one tweet immediately, then exit. Best for cron jobs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print a candidate without posting to X.",
    )
    args = parser.parse_args()

    load_dotenv(DOTENV_PATH)
    generator = build_text_generator()

    if args.once or args.dry_run:
        run_once(generator, dry_run=args.dry_run)
    else:
        run_scheduler(generator, dry_run=False)


if __name__ == "__main__":
    main()
