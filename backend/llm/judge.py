"""Pass 1: Judge. Classify each scanner candidate as confirm / reject / uncertain.

The Judge sees code context. The Synthesizer never will.
"""

from __future__ import annotations

import json
from typing import Iterable

from backend.llm.client import call_tool
from backend.models import Finding


_SYSTEM = """You are the Judge in a three-pass crypto-review pipeline called Quantum Sommelier.

A deterministic scanner has produced candidate findings from a public GitHub repo. Your job is to read the evidence and return a verdict for each:
- "confirm" — this is a real finding in production code
- "reject" — this is a false positive (e.g. test fixture, comment, unrelated string, example in docs)
- "uncertain" — the evidence is ambiguous and a human reviewer should decide

Scanner confidence tiers guide your bias:
- confidence=high → verify this is production code, not a test or example. Prefer confirm.
- confidence=medium → assess whether this is a real finding or a false positive.
- confidence=low → reject unless context strongly supports it.

You must not invent findings. You only emit verdicts on the findings provided.

Return verdicts via the `judge` tool."""


_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["confirm", "reject", "uncertain"]},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "verdict", "rationale"],
            },
        }
    },
    "required": ["verdicts"],
}


def _finding_block(f: Finding) -> dict:
    return {
        "id": f.id,
        "rule_id": f.rule_id,
        "category": f.category,
        "severity": f.severity,
        "confidence": f.confidence,
        "file_path": f.file_path,
        "line_start": f.line_start,
        "line_end": f.line_end,
        "language": f.language,
        "in_test_context": f.in_test_context,
        "algorithm": f.algorithm,
        "key_size": f.key_size,
        "curve": f.curve,
        "library": f.library,
        "version": f.version,
        "rule_description": f.rule_description,
        "code_snippet": f.code_snippet,
    }


def _judge_batch(findings: list[Finding]) -> dict[str, tuple[str, str]]:
    payload = {"findings": [_finding_block(f) for f in findings]}
    user = (
        "Review each candidate finding and emit a verdict. "
        "Be ruthless about test fixtures and examples.\n\n"
        + json.dumps(payload, indent=2)
    )
    out = call_tool(_SYSTEM, user, "judge", _SCHEMA, max_tokens=4096, temperature=0.1)
    verdicts = {}
    for v in out.get("verdicts", []):
        fid = v.get("id")
        if fid:
            verdicts[fid] = (v.get("verdict", "uncertain"), v.get("rationale", "")[:500])
    return verdicts


def judge(findings: list[Finding]) -> list[Finding]:
    """Return the input list with judge_verdict/rationale populated."""
    if not findings:
        return []
    BATCH = 10
    out: list[Finding] = []
    for i in range(0, len(findings), BATCH):
        batch = findings[i:i + BATCH]
        try:
            verdicts = _judge_batch(batch)
        except Exception as exc:
            # Fail-open: mark uncertain with the error so scoring still runs.
            for f in batch:
                f.judge_verdict = "uncertain"
                f.judge_rationale = f"judge_error: {exc}"
                out.append(f)
            continue
        for f in batch:
            v, r = verdicts.get(f.id, ("uncertain", "no verdict returned"))
            f.judge_verdict = v  # type: ignore[assignment]
            f.judge_rationale = r
            out.append(f)
    return out


def confirmed(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.judge_verdict == "confirm"]
