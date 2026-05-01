"""FastAPI entrypoint. Serves the static frontend + /api/v1/* endpoints."""

import secrets
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from backend.celery_app import celery, run_tasting
from backend.config import SETTINGS
from backend.cork import render as cork_render
from backend.github import fetcher, trending
from backend.models import (
    JobCompleteResponse, JobFailedResponse, JobQueuedResponse,
    JobRunningResponse, RepoMeta, Score, ScoreAxes, TastingNote,
    TastingNoteSection, Pairing, TastingRequest, TrendingRepo,
)
from backend.rate_limit import (
    GLOBAL_TASTINGS, PER_IP_TASTINGS, limiter, themed_429,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # PRD §8.4: on startup, sweep any orphaned work dirs from crashed workers.
    fetcher.sweep_work_root()
    yield


app = FastAPI(title="Quantum Sommelier", version="1.0.0", lifespan=_lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, themed_429)

# CORS open — single-container deploy, same-origin in practice.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Gzip everything ≥ 1 KB. Significant for HTML/CSS/JS/JSON.
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ── API ────────────────────────────────────────────────────────

@app.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "scanner_version": SETTINGS.scanner_version,
        "rubric_version": SETTINGS.rubric_version,
        "model": SETTINGS.anthropic_model,
    }


@app.get("/api/v1/rubric")
def rubric() -> dict:
    """Transparent rubric endpoint per PRD §6.5."""
    return {
        "rubric_version": SETTINGS.rubric_version,
        "scanner_version": SETTINGS.scanner_version,
        "axes": {
            "hndl_exposure": "Harvest-Now-Decrypt-Later exposure surface.",
            "signature_agility": "Ability to rotate or replace signature algorithms.",
            "crypto_hygiene": "General health of the cryptographic posture.",
            "pq_adoption_readiness": "Concrete post-quantum primitives already in use.",
        },
        "letter_grade_thresholds": {"A": 90, "B": 78, "C": 62, "D": 45, "F": 0},
        "severity_weights": {"critical": 28, "high": 18, "medium": 10, "low": 5, "info": 1},
    }


@app.get("/api/v1/trending", response_model=list[TrendingRepo])
def trending_repos(limit: int = 5) -> list[TrendingRepo]:
    return trending.rising_repos(limit=limit)


@app.post("/api/v1/tastings")
@limiter.limit(PER_IP_TASTINGS)
@limiter.shared_limit(GLOBAL_TASTINGS, scope="global_tastings")
def start_tasting(request: Request, body: TastingRequest = Body(...)) -> JSONResponse:
    try:
        owner, name = fetcher.normalize_repo_url(body.repo_url)
    except fetcher.RepoFetchError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})

    job_id = "tasting_" + secrets.token_urlsafe(12)
    task = run_tasting.apply_async(
        kwargs={"owner": owner, "name": name, "ref": body.ref or "main", "job_id": job_id},
        task_id=job_id,
    )
    return JSONResponse(
        status_code=202,
        content=JobQueuedResponse(
            job_id=task.id, status="queued", poll_url=f"/api/v1/tastings/{task.id}",
        ).model_dump(),
    )


@app.get("/api/v1/tastings/{job_id}")
def get_tasting(job_id: str) -> JSONResponse:
    task = celery.AsyncResult(job_id)
    if task.state == "PENDING":
        return JSONResponse(status_code=200, content=JobRunningResponse(
            job_id=job_id, status="running", stage="fetching", progress_pct=5,
        ).model_dump())
    if task.state == "PROGRESS":
        info: dict = task.info or {}
        return JSONResponse(status_code=200, content=JobRunningResponse(
            job_id=job_id,
            status="running",
            stage=info.get("stage", "scanning"),
            progress_pct=int(info.get("progress_pct", 20)),
        ).model_dump())
    if task.state == "FAILURE":
        err = str(task.info) if task.info else "unknown error"
        return JSONResponse(status_code=200, content=JobFailedResponse(
            job_id=job_id, status="failed",
            error={
                "code": "pipeline_error",
                "message": "The sommelier is indisposed. Please try again.",
                "detail": err[:400],
                "retryable": True,
            },
        ).model_dump())
    if task.state == "SUCCESS":
        try:
            tasting = TastingNote.model_validate(task.result)
        except Exception as exc:
            return JSONResponse(status_code=200, content=JobFailedResponse(
                job_id=job_id, status="failed",
                error={"code": "validation_failed", "message": "Could not read the tasting.", "detail": str(exc), "retryable": True},
            ).model_dump())
        return JSONResponse(status_code=200, content=JobCompleteResponse(
            job_id=job_id, status="complete", tasting=tasting,
        ).model_dump())
    # STARTED, RETRY, etc.
    return JSONResponse(status_code=200, content=JobRunningResponse(
        job_id=job_id, status="running", stage="scanning", progress_pct=15,
    ).model_dump())


def _load_tasting_or_404(job_id: str) -> TastingNote:
    task = celery.AsyncResult(job_id)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="tasting_not_ready_or_expired")
    return TastingNote.model_validate(task.result)


@app.get("/api/v1/tastings/{job_id}/cork.png")
def cork_png(job_id: str) -> Response:
    tasting = _load_tasting_or_404(job_id)
    png = cork_render.render_png(tasting)
    # Content type depends on whether resvg produced a PNG or fell back to SVG.
    ct = "image/png" if png[:8].startswith(b"\x89PNG") else "image/svg+xml"
    return Response(
        content=png,
        media_type=ct,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@app.get("/api/v1/tastings/{job_id}/cork.svg")
def cork_svg(job_id: str) -> Response:
    tasting = _load_tasting_or_404(job_id)
    return Response(
        content=cork_render.render_svg(tasting),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


# ── SEO endpoints (registered before the SPA fallback) ─────────

_ROBOTS_TXT = (
    "User-agent: *\n"
    "Allow: /\n"
    "Disallow: /api/\n"
    "Sitemap: https://quantum-sommelier.charlesmorris.dev/sitemap.xml\n"
)

_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://quantum-sommelier.charlesmorris.dev/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""


@app.get("/robots.txt", include_in_schema=False)
def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(
        _ROBOTS_TXT,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml() -> Response:
    return Response(
        content=_SITEMAP_XML,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ── Static frontend ────────────────────────────────────────────

_FRONTEND = Path(SETTINGS.frontend_dir)

# Asset extension → cache policy. Hashed bundle output gets immutable; the
# HTML shell never caches because it's the entry point that references the
# hashed bundles.
_IMMUTABLE_EXTS = {".js", ".css", ".woff", ".woff2", ".svg", ".png", ".jpg", ".webp", ".ico"}


def _cache_headers_for(path: Path) -> dict[str, str]:
    if path.suffix.lower() == ".html":
        return {"Cache-Control": "no-cache, must-revalidate"}
    if path.suffix.lower() in _IMMUTABLE_EXTS:
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {"Cache-Control": "public, max-age=3600"}


if _FRONTEND.is_dir():
    # Serve frontend from root; any path that isn't /api falls through here.
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND)), name="assets")

    @app.get("/")
    def root() -> FileResponse:
        html = _FRONTEND / "Quantum Sommelier.html"
        return FileResponse(str(html), headers=_cache_headers_for(html))

    @app.get("/{full_path:path}")
    def static_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = _FRONTEND / full_path
        if candidate.is_file():
            return FileResponse(str(candidate), headers=_cache_headers_for(candidate))
        # SPA fallback — return the main HTML (no-cache so users always get the latest shell).
        html = _FRONTEND / "Quantum Sommelier.html"
        return FileResponse(str(html), headers=_cache_headers_for(html))
