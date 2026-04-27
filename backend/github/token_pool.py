"""Round-robin pool over GitHub PATs with soft usage tracking."""

from __future__ import annotations

import itertools
import threading
from typing import Optional

from backend.config import SETTINGS


class TokenPool:
    def __init__(self, tokens: list[str]):
        self._tokens = [t for t in tokens if t]
        self._cycle = itertools.cycle(self._tokens) if self._tokens else None
        self._lock = threading.Lock()
        self._exhausted: set[str] = set()

    def next(self) -> Optional[str]:
        if not self._cycle:
            return None
        with self._lock:
            for _ in range(len(self._tokens)):
                tok = next(self._cycle)
                if tok not in self._exhausted:
                    return tok
            return None

    def mark_exhausted(self, token: str) -> None:
        with self._lock:
            self._exhausted.add(token)

    def any_left(self) -> bool:
        with self._lock:
            return any(t not in self._exhausted for t in self._tokens)


POOL = TokenPool(SETTINGS.github_tokens)
