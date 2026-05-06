from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import requests
import tweepy
from dotenv import set_key

from env_utils import required_env
from http_utils import raise_for_status


DOTENV_PATH = ".env"
X_TOKEN_URL = "https://api.x.com/2/oauth2/token"
X_TWEETS_URL = "https://api.x.com/2/tweets"
X_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


def upload_media_oauth2_bearer(access_token: str, media_path: str) -> str:
    path_obj = Path(media_path)
    with path_obj.open("rb") as handle:
        files = {"media": (path_obj.name, handle)}
        response = requests.post(
            X_MEDIA_UPLOAD_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            files=files,
            timeout=120,
        )
    raise_for_status(response, "X media upload")
    media_id = response.json().get("media_id_string")
    if not media_id:
        raise RuntimeError("X media upload returned no media_id_string.")
    return str(media_id)


class TwitterPoster(Protocol):
    def post(
        self,
        text: str,
        reply_to_id: str | None = None,
        media_path: str | None = None,
    ) -> str:
        ...


class OAuth1TwitterPoster:
    def __init__(self) -> None:
        self.client = tweepy.Client(
            consumer_key=required_env("TWITTER_API_KEY"),
            consumer_secret=required_env("TWITTER_API_SECRET"),
            access_token=required_env("TWITTER_ACCESS_TOKEN"),
            access_token_secret=required_env("TWITTER_ACCESS_TOKEN_SECRET"),
        )

    def post(
        self,
        text: str,
        reply_to_id: str | None = None,
        media_path: str | None = None,
    ) -> str:
        kwargs: dict[str, object] = {"text": text}
        if reply_to_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_id
        if media_path:
            media = self.client.media_upload(media_path)
            kwargs["media_ids"] = [media.media_id]
        response = self.client.create_tweet(**kwargs)
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

    def post(
        self,
        text: str,
        reply_to_id: str | None = None,
        media_path: str | None = None,
    ) -> str:
        self.refresh_access_token()
        payload: dict[str, object] = {"text": text}
        if media_path:
            media_id = upload_media_oauth2_bearer(self.access_token, media_path)
            payload["media"] = {"media_ids": [media_id]}
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
