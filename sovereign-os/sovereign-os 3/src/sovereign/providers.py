"""A tiny provider adapter. No provider sees memory until explicitly granted."""
from __future__ import annotations
import os
from typing import Callable

PROVIDERS = {
    "kimi": {"api_key": "KIMI_API_KEY", "model": "KIMI_MODEL", "base_url": "https://api.moonshot.ai/v1"},
    "openai": {"api_key": "OPENAI_API_KEY", "model": "OPENAI_MODEL", "base_url": "https://api.openai.com/v1"},
}


def available() -> list[dict]:
    options = [{"id": "local", "name": "Local evidence (no AI)", "cloud": False, "ready": True}]
    for provider, config in PROVIDERS.items():
        options.append({"id": provider, "name": provider.capitalize(), "cloud": True,
                        "ready": bool(os.getenv(config["api_key"]) and os.getenv(config["model"]))})
    return options


def generate(provider: str, messages: list[dict]) -> str:
    if provider not in PROVIDERS:
        raise ValueError("Unknown provider.")
    config = PROVIDERS[provider]
    key, model = os.getenv(config["api_key"]), os.getenv(config["model"])
    if not key or not model:
        raise ValueError("Provider not configured. See .env.example.")
    # Imported on demand so the offline/local path never creates an API client.
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=config["base_url"], timeout=25.0, max_retries=0)
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
    return response.choices[0].message.content or "(No text returned.)"
