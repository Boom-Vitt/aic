"""Anthropic Messages client for the pinned comparison.

The API key is read from the environment at request time and is not returned.
"""
from __future__ import annotations

import json
import os
from typing import NamedTuple, Protocol
import urllib.error
import urllib.request

from benchmarks.errors import RunError


class Completion(NamedTuple):
    text: str
    input_tokens: int
    output_tokens: int
    raw: dict


class ModelClient(Protocol):
    def complete(self, *, model: str, system: str, user: str, max_tokens: int) -> Completion:
        """Return one completion. Implementations must not retry."""


def require_key() -> None:
    """Exit-3 condition: a real key must already be in the environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or any(character.isspace() or ord(character) < 32 for character in key):
        raise RunError("ANTHROPIC_API_KEY is required.", 3)


class AnthropicClient:
    def __init__(self, *, url: str, version: str, timeout: float = 120.0):
        self.url = url
        self.version = version
        self.timeout = timeout

    def complete(self, *, model: str, system: str, user: str, max_tokens: int) -> Completion:
        require_key()
        key = os.environ["ANTHROPIC_API_KEY"]
        body = json.dumps(
            {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "content-type": "application/json",
                "anthropic-version": self.version,
                "x-api-key": key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read(500).decode("utf-8", errors="replace").replace(key, "[redacted]")
            raise RunError(f"Anthropic request failed with HTTP {exc.code}: {detail}", 1) from None
        except urllib.error.URLError as exc:
            raise RunError("Anthropic request failed before a response.", 1) from exc
        try:
            raw = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RunError("Anthropic response was not UTF-8 JSON.", 1) from exc
        if not isinstance(raw, dict):
            raise RunError("Anthropic response was not a JSON object.", 1)
        blocks = raw.get("content")
        if not isinstance(blocks, list):
            raise RunError("Anthropic response did not include content.", 1)
        text = []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                text.append(block["text"])
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if isinstance(input_tokens, bool) or not isinstance(input_tokens, int):
            input_tokens = 0
        if isinstance(output_tokens, bool) or not isinstance(output_tokens, int):
            output_tokens = 0
        return Completion(text="".join(text), input_tokens=input_tokens, output_tokens=output_tokens, raw=raw)
