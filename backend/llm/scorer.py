"""Deterministic scoring engine. No LLM.

Produces four axis scores (0-100, higher = better posture) and a letter grade.
The rubric is versioned (`qs-rubric-1.0.0`) so scores are reproducible.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from backend.config import SETTINGS
from backend.models import Finding, Score, ScoreAxes


# Severity weights (penalty magnitude per confirmed finding)
_SEV_W = {"critical": 28, "high": 18, "medium": 10, "low": 5, "info": 1}

# Rubric routing: each category contributes to specific axes.
# Axis names: hndl, sig, hyg, pqa
# PQC adoption counts as a BOOST to PQA and a small boost to HNDL/SIG.
_CATEGORY_AXIS_MAP = {
    "quantum_vulnerable":   {"hndl": -1.0, "sig": -1.0, "hyg": 0.0, "pqa": -0.4},
    "deprecated_primitive": {"hndl": -0.2, "sig": -0.3, "hyg": -1.0, "pqa": 0.0},
    "committed_secret":     {"hndl": -0.8, "sig": 0.0, "hyg": -1.0, "pqa": 0.0},
    "config_weakness":      {"hndl": -0.5, "sig": -0.2, "hyg": -0.8, "pqa": 0.0},
    "pqc_adoption":         {"hndl": 0.5,  "sig": 0.7, "hyg": 0.2, "pqa": 1.0},
    "hybrid_scheme":        {"hndl": 1.0,  "sig": 0.5, "hyg": 0.2, "pqa": 0.9},
    "suspected":            {"hndl": -0.1, "sig": -0.1, "hyg": -0.1, "pqa": 0.0},
}


def _letter(score: float) -> str:
    if score >= 90: return "A"
    if score >= 78: return "B"
    if score >= 62: return "C"
    if score >= 45: return "D"
    return "F"


def score_findings(findings: Iterable[Finding], in_test_discount: float = 0.4) -> Score:
    hndl = 100.0
    sig = 100.0
    hyg = 100.0
    pqa = 20.0  # starts low; must be earned

    pqc_adoption_count = 0
    hybrid_count = 0

    for f in findings:
        if f.judge_verdict == "reject":
            continue
        weight = _SEV_W.get(f.severity, 5)
        if f.judge_verdict == "uncertain":
            weight *= 0.5
        if f.in_test_context:
            weight *= in_test_discount
        routing = _CATEGORY_AXIS_MAP.get(f.category, _CATEGORY_AXIS_MAP["suspected"])

        hndl += routing["hndl"] * weight
        sig += routing["sig"] * weight
        hyg += routing["hyg"] * weight
        pqa += routing["pqa"] * weight

        if f.category == "pqc_adoption":
            pqc_adoption_count += 1
        if f.category == "hybrid_scheme":
            hybrid_count += 1

    # Bonus PQ adoption credit
    if pqc_adoption_count:
        pqa = min(100.0, pqa + 20 + 4 * pqc_adoption_count)
    if hybrid_count:
        hndl = min(100.0, hndl + 6 * hybrid_count)

    def clamp(v): return max(0, min(100, int(round(v))))
    axes = ScoreAxes(
        hndl_exposure=clamp(hndl),
        signature_agility=clamp(sig),
        crypto_hygiene=clamp(hyg),
        pq_adoption_readiness=clamp(pqa),
    )
    overall = 0.35 * axes.hndl_exposure + 0.25 * axes.signature_agility \
            + 0.25 * axes.crypto_hygiene + 0.15 * axes.pq_adoption_readiness

    return Score(
        letter_grade=_letter(overall),  # type: ignore[arg-type]
        axes=axes,
        rubric_version=SETTINGS.rubric_version,
        headline="",  # filled in by Synthesizer
    )


def severity_histogram(findings: Iterable[Finding]) -> dict[str, int]:
    return dict(Counter(f.severity for f in findings if f.judge_verdict != "reject"))
