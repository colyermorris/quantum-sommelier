"""Pass 2: Synthesizer. Composes the tasting note from confirmed findings.

Critical rule: the Synthesizer NEVER sees raw source code. It only sees the
curated evidence pack (IDs, algorithms, categories, severities, and the
rule_description sentence). Prose references findings by ID via {{ref:ID}}
placeholders; the Validator+Hydrator rejects unbacked citations.
"""

from __future__ import annotations

import json

from backend.llm.client import call_tool
from backend.models import Finding, RepoMeta, Score


_SYSTEM = """You are the Sommelier — the voice of the Quantum Sommelier. You write tasting notes about GitHub repositories as if they were wines, evaluating their post-quantum cryptographic readiness.

VOICE: Dry, confident, editorial magazine. Funny in a deadpan way, never goofy. Treat cryptographic decisions with the seriousness of a sommelier discussing terroir. Mix wine vocabulary with technical precision. Allow a single sharp line per section.

HARD RULES — these are non-negotiable:

1. Reference findings ONLY by their exact ID using {{ref:ID}} placeholders. Never paraphrase file paths, line numbers, or code content. Never invent findings.
2. The grade letter is inserted via {{grade}} placeholder in the finish — do not spell out the letter yourself.
3. Never hallucinate a version number, CVE, author name, or dependency that isn't in the evidence pack.
4. Keep the voice consistent: Nose is first-impression (1 paragraph), Palate is the body (2-4 paragraphs), Finish is the verdict (1 paragraph), Pairing has three fields (prose, compliance, beverage).
5. The pull_quote is a single arresting sentence under 120 characters, quotable on its own.
6. Pairing.beverage is one sentence naming a real wine/drink with a one-line sommelier rationale tying it to the repo's posture.

STYLE EXEMPLAR (do not copy verbatim, match the register):
"A 2021 Python project with aggressive RSA-2048 on the nose and a faint whiff of MD5 in the middleware. The dependency manifest reads like a wine list from a restaurant that closed during the pandemic."

Return the tasting note via the `compose_tasting` tool."""


_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {
            "type": "string",
            "description": "Short sommelier verdict headline, 3-7 words, title-style.",
        },
        "nose": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1 paragraph. The first impression.",
        },
        "palate": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 paragraphs. The body — primary + secondary notes, any bright notes.",
        },
        "finish": {
            "type": "string",
            "description": "1 paragraph. The verdict. Must include {{grade}} placeholder exactly once.",
        },
        "pairing_prose": {"type": "string"},
        "pairing_compliance": {"type": "string"},
        "pairing_beverage": {"type": "string"},
        "pull_quote": {
            "type": "string",
            "description": "One arresting sentence under 120 chars. Quotable alone.",
        },
    },
    "required": [
        "headline", "nose", "palate", "finish",
        "pairing_prose", "pairing_compliance", "pairing_beverage",
        "pull_quote",
    ],
}


def _evidence_pack(repo: RepoMeta, score: Score, findings: list[Finding]) -> dict:
    return {
        "repo": {
            "owner": repo.owner, "name": repo.name, "ref": repo.ref,
            "commit_sha": repo.commit_sha, "language": repo.primary_language,
            "stars": repo.stars, "description": repo.description,
        },
        "score": {
            "letter_grade": score.letter_grade,
            "axes": score.axes.model_dump(),
            "rubric_version": score.rubric_version,
        },
        "findings": [
            {
                "id": f.id,
                "short": f.rule_description,
                "severity": f.severity,
                "category": f.category,
                "algorithm": f.algorithm,
                "library": f.library,
                "version": f.version,
                "judge_rationale": f.judge_rationale,
            }
            for f in findings
        ],
    }


def synthesize(repo: RepoMeta, score: Score, findings: list[Finding]) -> dict:
    pack = _evidence_pack(repo, score, findings)
    user = (
        "Compose a tasting note for this repo based on the evidence pack below. "
        "Cite findings by ID using {{ref:ID}}. Include {{grade}} in the finish. "
        "Keep the voice dry, editorial, and precise.\n\n"
        + json.dumps(pack, indent=2)
    )
    return call_tool(_SYSTEM, user, "compose_tasting", _SCHEMA, max_tokens=3000, temperature=0.7)
