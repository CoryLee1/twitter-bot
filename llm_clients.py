import json
import os
import random
from typing import Protocol

import requests
from openai import OpenAI

from env_utils import required_env
from http_utils import raise_for_status
from socialmedia_pic import image_file_to_data_url


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


class DoubaoTextGenerator:
    def __init__(self) -> None:
        self.api_key = required_env("ARK_API_KEY")
        self.base_url = os.getenv(
            "ARK_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/v3/responses",
        )
        self.model = os.getenv("ARK_MODEL", "doubao-seed-2-0-pro-260215")
        self.vision_model = os.getenv(
            "ARK_VISION_MODEL",
            "doubao-seed-1-6-flash-250828",
        )

    def generate(self, prompt: str) -> str:
        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            },
            timeout=120,
        )
        raise_for_status(response, "Doubao Ark")
        return extract_responses_text(response.json())

    def generate_with_image(self, prompt: str, image_path: str) -> str:
        model = self.vision_model
        data_url = image_file_to_data_url(image_path)
        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": data_url,
                            },
                            {
                                "type": "input_text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            },
            timeout=120,
        )
        raise_for_status(response, "Doubao Ark vision")
        return extract_responses_text(response.json())


def extract_responses_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        texts: list[str] = []
        for item in output:
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    texts.append(text)
        if texts:
            return "\n".join(texts)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content

    raise RuntimeError("Doubao Ark returned no text output.")


class TemplateTextGenerator:
    def generate(self, prompt: str) -> str:
        templates = [
            (
                "My toxic trait is keeping 47 tabs open because each one represents "
                "a different version of who I might become."
            ),
            (
                "POV: you opened one article for research and now Chrome looks like "
                "a final boss health bar."
            ),
            (
                "If your browser tabs have started forming a society, it might be "
                "time to let Leo clean them up."
            ),
            (
                "Everyone talks about optimizing workflows, but the real boss fight "
                "is finding that one tab from yesterday."
            ),
            (
                "A tiny elephant that turns tab chaos into a visual board should not "
                "make this much sense, but here we are."
            ),
            (
                "Your bookmarks should feel more like an inspiration wall and less "
                "like a filing cabinet nobody wants to open."
            ),
        ]
        random.shuffle(templates)
        candidates = [
            {
                "text": text,
                "score": 8 + (index % 2),
                "rationale": "Template mode: no paid AI API required.",
            }
            for index, text in enumerate(templates[:3])
        ]
        return json.dumps({"candidates": candidates})


def build_text_generator() -> TextGenerator:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return OpenAITextGenerator()
    if provider == "ollama":
        return OllamaTextGenerator()
    if provider in {"doubao", "ark"}:
        return DoubaoTextGenerator()
    if provider == "template":
        return TemplateTextGenerator()

    raise RuntimeError("LLM_PROVIDER must be template, doubao, ollama, or openai")
