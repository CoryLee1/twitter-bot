from __future__ import annotations

import os
from typing import Protocol

import requests
import tweepy
from dotenv import set_key

from env_utils import required_env
from http_utils import raise_for_status


DOTENV_PATH = ".env"
X_TOKEN_URL = "https://api.x.com/2/oauth2/token"
X_TWEETS_URL = "https://api.x.com/2/tweets"


class TwitterPoster(Protocol):
    def post(self, text: str, reply_to_id: str | None = None) -> str:
        ...


class OAuth1TwitterPoster:
    def __init__(self) -> None:
        self.client = tweepy.Client(
            consumer_key=required_env("TWITTER_API_KEY"),
            consumer_secret=required_env("TWITTER_API_SECRET"),
            access_token=required_env("TWITTER_ACCESS_TOKEN"),
            access_token_secret=required_env("TWITTER_ACCESS_TOKEN_SECRET"),
        )

    def post(self, text: str, reply_to_id: str | None = None) -> str:
        response = self.client.create_tweet(
            text=text,
            in_reply_to_tweet_id=reply_to_id,
        )
        return response.data["id"]


class OAuth2TwitterPoster:
    def __init__(self) -> None:
        self.client_id = required_env("TWITTER_CLIENT_ID")
        self.client_secret = os.getenv("TWITTER_CLIENT_SECRET")
        self.access_token = required_env("TWITTER_ACCESS_TOKEN")
        self.refresh_token = os.getenv("TWITTER_REFRESH_TOKEN")

    def refresh_access_token(self) -> None:
        if not self.refresh_token:
            return

        auth = (self.client_id, self.client_secret) if self.client_secret else None
        response = requests.post(
            X_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
            },
            auth=auth,
            timeout=30,
        )
        raise_for_status(response, "X OAuth token refresh")
        token_data = response.json()

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)

        os.environ["TWITTER_ACCESS_TOKEN"] = self.access_token
        set_key(DOTENV_PATH, "TWITTER_ACCESS_TOKEN", self.access_token)
        if self.refresh_token:
            os.environ["TWITTER_REFRESH_TOKEN"] = self.refresh_token
            set_key(DOTENV_PATH, "TWITTER_REFRESH_TOKEN", self.refresh_token)

    def post(self, text: str, reply_to_id: str | None = None) -> str:
        self.refresh_access_token()
        payload: dict[str, object] = {"text": text}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

        response = requests.post(
            X_TWEETS_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            json=payload,
            timeout=30,
        )
        raise_for_status(response, "X create tweet")
        return response.json()["data"]["id"]


def build_twitter_poster() -> TwitterPoster:
    auth_mode = os.getenv("TWITTER_AUTH_MODE", "oauth2").lower()
    if auth_mode == "oauth1":
        return OAuth1TwitterPoster()
    if auth_mode == "oauth2":
        return OAuth2TwitterPoster()

    raise RuntimeError("TWITTER_AUTH_MODE must be either oauth1 or oauth2")
