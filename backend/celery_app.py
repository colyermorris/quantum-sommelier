"""Celery app + task definition for the tasting pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from celery import Celery

from backend.config import SETTINGS
from backend.github import fetcher
from backend.llm import pipeline
from backend.models import RepoMeta


celery = Celery(
    "quantum_sommelier",
    broker=SETTINGS.redis_url,
    backend=SETTINGS.redis_url,
)
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]
celery.conf.task_time_limit = SETTINGS.scan_timeout_s + 60
celery.conf.task_soft_time_limit = SETTINGS.scan_timeout_s + 30
celery.conf.worker_max_tasks_per_child = 25


@celery.task(bind=True, name="run_tasting")
def run_tasting(self, *, owner: str, name: str, ref: str, job_id: str) -> dict:
    def report(stage: str, pct: int):
        self.update_state(state="PROGRESS", meta={"stage": stage, "progress_pct": pct, "job_id": job_id})

    report("fetching", 10)
    try:
        cloned = fetcher.clone(owner, name, ref, job_id)
    except fetcher.RepoFetchError as exc:
        raise RuntimeError(f"{exc.code}: {exc.message}")

    try:
        repo = RepoMeta(
            owner=cloned.owner,
            name=cloned.name,
            url=cloned.url,
            ref=cloned.ref,
            commit_sha=cloned.commit_sha,
            primary_language=cloned.primary_language,
            stars=cloned.stars,
            description=cloned.description,
        )
        tasting = pipeline.run(cloned.path, repo, report_stage=report)
    finally:
        fetcher.cleanup(cloned.path)

    return tasting.model_dump()
