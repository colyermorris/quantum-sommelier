"""Load the curated crypto library database."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


DB_PATH = Path(__file__).parent.parent / "data" / "crypto_library_db.yml"


@lru_cache(maxsize=1)
def load() -> dict:
    with DB_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    by_name: dict[str, dict] = {}
    for lib in raw.get("libraries", []):
        by_name[lib["name"].lower()] = lib
    return {"libraries_by_name": by_name, "raw": raw}


def lookup(name: str) -> dict | None:
    return load()["libraries_by_name"].get(name.lower())


def quantum_status_for_library(name: str) -> str | None:
    lib = lookup(name)
    if not lib:
        return None
    statuses = {e["quantum_status"] for e in lib.get("exposes", [])}
    if "pqc" in statuses:
        return "pqc"
    if "vulnerable" in statuses:
        return "vulnerable"
    if "deprecated" in statuses:
        return "deprecated"
    return "symmetric_safe"
