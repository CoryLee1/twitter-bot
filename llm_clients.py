import os
from typing import Protocol

import requests
from openai import OpenAI

from env_utils import required_env
from http_utils import raise_for_status


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class OpenAITextGenerator:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=required_env("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You write concise, native-feeling X/Twitter posts.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
            temperature=0.9,
        )
        return response.choices[0].message.content or ""


class OllamaTextGenerator:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.ollama_url.rstrip('/')}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.9,
                    "num_predict": 700,
                },
            },
            timeout=120,
        )
        raise_for_status(response, "Ollama")
        return response.json().get("response", "")


def build_text_generator() -> TextGenerator:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return OpenAITextGenerator()
    if provider == "ollama":
        return OllamaTextGenerator()

    raise RuntimeError("LLM_PROVIDER must be either ollama or openai")
