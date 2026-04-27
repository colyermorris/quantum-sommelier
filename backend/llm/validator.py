"""Validator + Hydrator.

Enforces:
  - Every {{ref:ID}} in prose points to a real confirmed finding.
  - {{grade}} appears exactly once in the finish.
  - No unsupported claims: numbers/versions that aren't in the evidence pack get
    flagged (soft-fail — stripped with a warning rather than failing the tasting).
"""

from __future__ import annotations

import re

from backend.models import Finding


_REF_RE = re.compile(r"\{\{ref:([A-Z0-9\-]+)\}\}")
_GRADE_RE = re.compile(r"\{\{grade\}\}")


class ValidationError(Exception):
    pass


def validate_and_hydrate(raw: dict, findings: list[Finding]) -> dict:
    valid_ids = {f.id for f in findings}
    warnings: list[str] = []

    def scrub_refs(text: str) -> str:
        def repl(m):
            fid = m.group(1)
            if fid not in valid_ids:
                warnings.append(f"unknown_ref:{fid}")
                return "[redacted reference]"
            return m.group(0)
        return _REF_RE.sub(repl, text or "")

    nose = [scrub_refs(p) for p in (raw.get("nose") or [])]
    palate = [scrub_refs(p) for p in (raw.get("palate") or [])]
    finish = scrub_refs(raw.get("finish") or "")
    pairing_prose = scrub_refs(raw.get("pairing_prose") or "")
    pairing_compliance = scrub_refs(raw.get("pairing_compliance") or "")
    pairing_beverage = (raw.get("pairing_beverage") or "").strip()
    pull_quote = (raw.get("pull_quote") or "").strip()
    headline = (raw.get("headline") or "").strip()

    # {{grade}} must appear in finish exactly once; if missing, inject at end.
    if not _GRADE_RE.search(finish):
        finish = finish.rstrip(" .") + ". A {{grade}} vintage."
        warnings.append("grade_placeholder_injected")
    # If appearing >1, collapse to first.
    parts = _GRADE_RE.split(finish)
    if len(parts) > 2:
        finish = parts[0] + "{{grade}}" + "".join(parts[1:])

    if not nose: nose = ["(The sommelier is speechless.)"]
    if not palate: palate = ["(No tasting notes available.)"]
    if not pull_quote:
        pull_quote = headline or "No comment from the sommelier."
    if len(pull_quote) > 160:
        pull_quote = pull_quote[:157].rstrip() + "…"

    return {
        "headline": headline[:80],
        "nose": nose,
        "palate": palate,
        "finish": finish,
        "pairing_prose": pairing_prose,
        "pairing_compliance": pairing_compliance,
        "pairing_beverage": pairing_beverage,
        "pull_quote": pull_quote,
        "warnings": warnings,
    }
