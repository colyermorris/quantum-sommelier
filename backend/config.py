"""Runtime configuration. All tunables live here, sourced from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key) or default)
    except ValueError:
        return default


def _env_list(key: str) -> list[str]:
    raw = _env(key)
    return [p.strip() for p in raw.split(",") if p.strip()] if raw else []


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"))

    github_tokens: list[str] = field(default_factory=lambda: _env_list("GITHUB_TOKEN"))

    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://127.0.0.1:6379/0"))

    work_dir: str = field(default_factory=lambda: _env("QS_WORK_DIR", "/tmp/qs-work"))
    max_repo_bytes: int = field(default_factory=lambda: _env_int("QS_MAX_REPO_BYTES", 500 * 1024 * 1024))
    scan_timeout_s: int = field(default_factory=lambda: _env_int("QS_SCAN_TIMEOUT_S", 120))

    per_ip_tastings_per_hour: int = field(default_factory=lambda: _env_int("QS_PER_IP_LIMIT", 5))
    global_tastings_per_hour: int = field(default_factory=lambda: _env_int("QS_GLOBAL_LIMIT", 7))

    llm_input_token_budget: int = field(default_factory=lambda: _env_int("QS_LLM_INPUT_BUDGET", 50_000))
    llm_output_token_budget: int = field(default_factory=lambda: _env_int("QS_LLM_OUTPUT_BUDGET", 10_000))

    scanner_version: str = "qs-scanner-1.0.0"
    rubric_version: str = "qs-rubric-1.0.0"

    frontend_dir: str = field(default_factory=lambda: _env("QS_FRONTEND_DIR", "/app/frontend"))


SETTINGS = Settings()
