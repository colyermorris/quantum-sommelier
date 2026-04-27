"""Pydantic models for the API + internal pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["critical", "high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]
Category = Literal[
    "quantum_vulnerable",
    "deprecated_primitive",
    "pqc_adoption",
    "hybrid_scheme",
    "committed_secret",
    "config_weakness",
    "suspected",
]
DetectionLayer = Literal["manifest", "source", "config", "cert"]
Language = Literal["python", "javascript", "typescript", "config", "manifest"]
JudgeVerdict = Literal["confirm", "reject", "uncertain"]


class Finding(BaseModel):
    id: str
    rule_id: str
    category: Category
    severity: Severity
    confidence: Confidence

    file_path: str
    line_start: int = 1
    line_end: int = 1
    code_snippet: str = ""
    language: Language = "python"
    in_test_context: bool = False

    algorithm: Optional[str] = None
    key_size: Optional[int] = None
    curve: Optional[str] = None
    library: Optional[str] = None
    version: Optional[str] = None

    detection_layer: DetectionLayer
    rule_description: str
    remediation_class: str = "review"

    # Populated by Judge
    judge_verdict: Optional[JudgeVerdict] = None
    judge_rationale: Optional[str] = None


class RepoMeta(BaseModel):
    owner: str
    name: str
    url: str
    ref: str = "main"
    commit_sha: str = ""
    primary_language: str = "unknown"
    stars: int = 0
    description: str = ""


class ScoreAxes(BaseModel):
    hndl_exposure: int = 0
    signature_agility: int = 0
    crypto_hygiene: int = 0
    pq_adoption_readiness: int = 0


class Score(BaseModel):
    letter_grade: Literal["A", "B", "C", "D", "F"]
    axes: ScoreAxes
    rubric_version: str
    headline: str = ""


class TastingNoteSection(BaseModel):
    prose: list[str] = Field(default_factory=list)


class Pairing(BaseModel):
    prose: str = ""
    compliance: str = ""
    beverage: str = ""


class TastingNote(BaseModel):
    repo: RepoMeta
    scanned_at: str
    scanner_version: str
    rubric_version: str
    score: Score
    nose: TastingNoteSection
    palate: TastingNoteSection
    finish: TastingNoteSection
    pairing: Pairing
    pull_quote: str
    findings: list[Finding]


# API request/response


class TastingRequest(BaseModel):
    repo_url: str
    ref: Optional[str] = "main"


class JobQueuedResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
    poll_url: str


class JobRunningResponse(BaseModel):
    job_id: str
    status: Literal["running"]
    stage: Literal["fetching", "scanning", "judging", "scoring", "synthesizing", "validating"]
    progress_pct: int


class JobFailedResponse(BaseModel):
    job_id: str
    status: Literal["failed"]
    error: dict


class JobCompleteResponse(BaseModel):
    job_id: str
    status: Literal["complete"]
    tasting: TastingNote


class TrendingRepo(BaseModel):
    name: str
    owner: str
    url: str
    lang: str
    stars: int
    blurb: str
