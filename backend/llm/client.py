"""Anthropic client wrapper. All LLM work uses Claude Haiku."""

from __future__ import annotations

import json
from typing import Any, Optional

from anthropic import Anthropic

from backend.config import SETTINGS


_client: Optional[Anthropic] = None


def client() -> Anthropic:
    global _client
    if _client is None:
        if not SETTINGS.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
        _client = Anthropic(api_key=SETTINGS.anthropic_api_key)
    return _client


def call_tool(
    system: str,
    user: str,
    tool_name: str,
    tool_input_schema: dict,
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> dict:
    """Force a single tool call; return the input dict."""
    resp = client().messages.create(
        model=SETTINGS.anthropic_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{
            "name": tool_name,
            "description": f"Emit structured output as {tool_name}.",
            "input_schema": tool_input_schema,
        }],
        tool_choice={"type": "tool", "name": tool_name},
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return dict(block.input)
    raise RuntimeError("LLM did not return a tool call")


def call_text(system: str, user: str, max_tokens: int = 2048, temperature: float = 0.5) -> str:
    resp = client().messages.create(
        model=SETTINGS.anthropic_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()
