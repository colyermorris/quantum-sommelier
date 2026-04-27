"""End-to-end pipeline: scan → judge → score → synthesize → validate → hydrate."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.config import SETTINGS
from backend.llm import judge as judge_mod
from backend.llm import synthesizer as synth_mod
from backend.llm import validator as val_mod
from backend.llm.scorer import score_findings
from backend.models import Pairing, RepoMeta, TastingNote, TastingNoteSection
from backend.scanner import scan_repo


def run(
    root: Path,
    repo: RepoMeta,
    report_stage=None,
) -> TastingNote:
    def stage(name: str, pct: int) -> None:
        if report_stage:
            try: report_stage(name, pct)
            except Exception: pass

    stage("scanning", 20)
    candidates = scan_repo(root)

    stage("judging", 40)
    judged = judge_mod.judge(candidates)
    confirmed_findings = judge_mod.confirmed(judged)

    # Edge case: if zero findings confirmed, synthesize still runs with an empty set.
    stage("scoring", 55)
    score = score_findings(judged)

    stage("synthesizing", 75)
    draft = synth_mod.synthesize(repo, score, confirmed_findings or judged)

    stage("validating", 90)
    hydrated = val_mod.validate_and_hydrate(draft, judged)

    score.headline = hydrated["headline"] or score.headline

    return TastingNote(
        repo=repo,
        scanned_at=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        scanner_version=SETTINGS.scanner_version,
        rubric_version=SETTINGS.rubric_version,
        score=score,
        nose=TastingNoteSection(prose=hydrated["nose"]),
        palate=TastingNoteSection(prose=hydrated["palate"]),
        finish=TastingNoteSection(prose=[hydrated["finish"]]),
        pairing=Pairing(
            prose=hydrated["pairing_prose"],
            compliance=hydrated["pairing_compliance"],
            beverage=hydrated["pairing_beverage"],
        ),
        pull_quote=hydrated["pull_quote"],
        findings=judged,
    )
