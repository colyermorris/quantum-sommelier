# Architecture

Quantum Sommelier is a single-container web app: paste a public GitHub URL, get a tasting note. This doc describes the system end-to-end — process layout, data flow, components, key design decisions, and the deploy topology.

---

## High-level

```
                ┌────────────────────────────────────────┐
   user ──▶ nginx (host) ──▶  container :8080           │
                │                                        │
                │  ┌─────────── supervisord ──────────┐  │
                │  │                                  │  │
                │  │  redis (loopback :6379)          │  │
                │  │     ▲           ▲                │  │
                │  │     │ broker    │ result backend │  │
                │  │     │           │                │  │
                │  │  uvicorn ──enqueue──▶ celery     │  │
                │  │  FastAPI            worker       │  │
                │  │     │                  │         │  │
                │  │     │                  ├─ git clone (shallow, bounded)
                │  │     │                  ├─ tree-sitter scan
                │  │     │                  ├─ Haiku judge (drop false +)
                │  │     │                  ├─ deterministic scorer
                │  │     │                  ├─ Haiku synthesize prose
                │  │     │                  ├─ validate + hydrate
                │  │     │                  └─ resvg cork render
                │  │     │                                │  │
                │  │     ▼                                │  │
                │  │  static frontend (Quantum Sommelier.html + bundle)  │
                │  └──────────────────────────────────┘  │
                └────────────────────────────────────────┘
```

Three processes live inside one container, supervised by `supervisord`:

| Process | Binds | Role |
|---|---|---|
| `redis-server` | `127.0.0.1:6379` | Celery broker + result backend + slowapi rate-limit storage |
| `uvicorn` (FastAPI) | `0.0.0.0:8080` | REST API + serves the static frontend bundle |
| `celery worker` | n/a | Runs the tasting pipeline (long-running, async) |

Single-container is deliberate — see [Design decisions](#design-decisions).

---

## Components

### Frontend — `Quantum Sommelier.html` + JSX bundle

- Single HTML entry (`Quantum Sommelier.html`) loads a hashed JS/CSS bundle built by `build.mjs` (esbuild).
- Source: `app.jsx`, `landing.jsx`, `scanning.jsx`, `tasting.jsx`, `overlays.jsx`, `data.js`, `edu.js`, `api.js`.
- Styles: `styles.css`, `styles-components.css`, `styles-tasting.css`, `styles-cork.css`, `styles-mobile.css`.
- Pages:
  - **Landing** — paste a repo URL or pick a "Rising on GitHub" repo from the trending strip.
  - **Scanning** — animated themed status while the worker chews; progress driven by `/api/v1/tastings/{id}` polling.
  - **Tasting** — letter grade, four sub-scores, evidence-backed nose/palate/finish/pairing, evidence list with file/line citations, cork share card.
- All API traffic is same-origin (`/api/v1/*`); CORS is open for dev convenience.

### Backend — `backend/`

```
backend/
├── main.py                # FastAPI app + static frontend mount + SEO endpoints
├── celery_app.py          # Celery app + run_tasting task
├── config.py              # env-driven Settings (frozen dataclass)
├── models.py              # pydantic schemas (TastingNote, Score, Finding, …)
├── rate_limit.py          # slowapi limiter + themed 429 response
├── github/
│   ├── fetcher.py         # url normalize, shallow clone, byte/timeout caps, sweep
│   ├── token_pool.py      # rotating GH PAT pool to absorb rate limits
│   └── trending.py        # curated rising-repos list (cached)
├── scanner/               # AST-first crypto scanner
│   ├── walker.py          # file walk + tree-sitter dispatch
│   ├── source.py          # per-language source rules
│   ├── certs.py           # X.509 / PEM parsing
│   ├── config_scan.py     # YAML/JSON/TOML config heuristics
│   ├── db.py              # rule registry / severity table
│   └── manifest.py        # package manifest detection (go.mod, pyproject, etc.)
├── llm/
│   ├── client.py          # anthropic SDK wrapper
│   ├── judge.py           # stage 1: vote on scanner candidates (drop false +)
│   ├── scorer.py          # deterministic numeric scoring against rubric
│   ├── synthesizer.py     # stage 2: prose generation (nose/palate/finish/pairing)
│   ├── validator.py       # JSON-schema validate + hydrate scanner-truth fields
│   └── pipeline.py        # orchestrator: scan → judge → score → synth → validate
└── cork/
    ├── render.py          # SVG → PNG via resvg-py (with SVG fallback)
    └── template.svg       # cork share-card template
```

### Storage

There is **no persistent storage**.

- Repo clones live in a tmpfs at `/tmp/qs-work/<job_id>/`, swept on container start and after each tasting.
- Tasting results live only in Redis as Celery results (default TTL).
- No database, no user accounts, no telemetry pipeline.

This is a deliberate constraint to keep the threat model small (see `security.md`).

---

## Data flow — one tasting

1. **`POST /api/v1/tastings`** with `{ repo_url }`.
   - SlowAPI checks per-IP (5/hour) **and** global (7/hour) limits. Themed 429 if exhausted.
   - URL normalized to `(owner, name)` via `github/fetcher.normalize_repo_url`.
   - Job ID minted (`tasting_<token>`); Celery task enqueued; **202 Accepted** with `poll_url`.

2. **Worker picks up the task** (`run_tasting` in `celery_app.py`):
   - **Fetch** — `fetcher.clone()`: shallow clone with `--depth=1`, hard caps on bytes (`QS_MAX_REPO_BYTES=500MB`) and wall-clock (`QS_SCAN_TIMEOUT_S=120s`). Uses GH PAT to lift unauth rate limits.
   - **Scan** — `scanner.scan_repo()`: tree-sitter walks supported languages, yields candidate `Finding`s (each carrying file path, line number, primitive name, language, raw snippet).
   - **Judge** (LLM 1) — `llm.judge.judge()`: passes candidate snippets to Claude Haiku 4.5 with a strict JSON schema; LLM votes `confirm | drop | unsure` per candidate. Drops drop the candidate; unsures are kept with degraded confidence.
   - **Score** (deterministic) — `llm.scorer.score_findings()`: computes numeric score across four axes from confirmed findings + rubric weights. **No LLM is involved in numeric scoring** — this is what stops grade drift.
   - **Synthesize** (LLM 2) — `llm.synthesizer.synthesize()`: passes the score + confirmed findings (no raw source) to Haiku. Output is JSON: nose bullets, palate bullets, finish, pairing, pull quote, headline. Schema-constrained.
   - **Validate + hydrate** — `llm.validator.validate_and_hydrate()`: JSON-validates the synthesizer output, re-attaches scanner-truth fields (file/line/severity) so the LLM can't tamper with them.
   - **Compose** — `pipeline.run()` builds a `TastingNote` pydantic model and returns it as the Celery task result.
   - Cleanup: `fetcher.cleanup()` deletes the clone from tmpfs (`finally` block — runs even on exception).

3. **Frontend polls** `GET /api/v1/tastings/{job_id}`:
   - Returns `running` with stage + `progress_pct` while in flight.
   - Returns `complete` with the full `TastingNote` on success.
   - Returns `failed` with a themed message on error.

4. **Cork share card** — `GET /api/v1/tastings/{job_id}/cork.{png,svg}`:
   - Loads the cached `TastingNote`, renders `cork/template.svg` with score/grade/repo, converts SVG → PNG via `resvg-py`. If resvg is unavailable, falls back to SVG with the same `Cache-Control`.

---

## API surface

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/health` | Returns `status`, `scanner_version`, `rubric_version`, active model. |
| `GET` | `/api/v1/rubric` | Full rubric — axes, severity weights, letter-grade thresholds. PRD §6.5. |
| `GET` | `/api/v1/trending?limit=5` | Curated rising-repos list. |
| `POST` | `/api/v1/tastings` | Body `{ repo_url, ref? }` → `202` + `job_id`. Rate limited. |
| `GET` | `/api/v1/tastings/{job_id}` | Status + progress + (eventually) result. |
| `GET` | `/api/v1/tastings/{job_id}/cork.png` | Share card (PNG, week-long immutable cache). |
| `GET` | `/api/v1/tastings/{job_id}/cork.svg` | Same, SVG. |
| `GET` | `/robots.txt`, `/sitemap.xml` | SEO. |
| `GET` | `/{path}` | Static frontend, with SPA fallback to `Quantum Sommelier.html`. |

---

## Configuration

All tunables come from environment (`backend/config.py`):

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | Pipeline LLM. |
| `GITHUB_TOKEN` | — | One or more comma-separated PATs; rotated per-clone. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Broker + result + rate-limit storage. |
| `QS_WORK_DIR` | `/tmp/qs-work` | Scratch tmpfs for clones. |
| `QS_MAX_REPO_BYTES` | `524288000` | Hard 500 MB clone cap. |
| `QS_SCAN_TIMEOUT_S` | `120` | Per-tasting wall clock. |
| `QS_PER_IP_LIMIT` | `5` | Tastings/hour/IP. |
| `QS_GLOBAL_LIMIT` | `7` | Tastings/hour total — caps Anthropic spend. |
| `QS_LLM_INPUT_BUDGET` | `50000` | Max input tokens passed to the LLM. |
| `QS_LLM_OUTPUT_BUDGET` | `10000` | Max output tokens. |

---

## Deploy topology

Production runs on a single EC2 box (`3.138.161.64`, AL2023) which also serves the personal portfolio at `charlesmorris.dev`. **Both apps share one host**:

```
                     ┌──────────────── EC2 (AL2023) ────────────────┐
  TLS (LE)           │                                              │
  ─────▶ nginx ───┬──▶ /  (Vite static build) ─────────── portfolio │
                  │                                                 │
                  └──▶ quantum-sommelier.charlesmorris.dev          │
                       127.0.0.1:8080  (docker container)           │
                       │                                            │
                       └─ supervisord ─ redis + uvicorn + celery    │
                                                                    │
                     └────────────────────────────────────────────────┘
```

- nginx terminates TLS; the QS subdomain reverse-proxies to the container on `127.0.0.1:8080`.
- The portfolio is unrelated and served as static files by nginx — **never touch its vhost**.
- Single-container compose override (`docker-compose.prod.yml`) binds the published port to `127.0.0.1` only so the container is unreachable except through nginx.
- Health: `HEALTHCHECK` polls `/api/v1/health` every 30s.
- See [`deployment.md`](./deployment.md) for the runbook and [`rollback.md`](./rollback.md) for cold-start recovery.

---

## Design decisions

### One container, three processes

Picked over docker-compose-with-three-services because:
- One artifact to ship, one health check, one log stream.
- Redis is loopback-only — no network exposure, no auth needed.
- The host runs another app — adding multiple containers raises the cognitive load of the shared box.

Trade: scaling individual processes requires breaking the container apart. Acceptable at current load.

### AST-first scanner, LLM second

The LLM never sees raw repo content. It only sees structured candidates that tree-sitter already extracted. Two payoffs:
- **Token cost is bounded** — even a 500 MB monorepo produces a fixed-size candidate set.
- **Hallucinated findings are nearly impossible** — the synthesizer cannot invent a finding because it never sees the source to invent one from.

Trade: every supported language needs explicit rules. Worth it.

### Deterministic scorer

The numeric score is **not** an LLM output. `backend/llm/scorer.py` computes it from confirmed findings × rubric weights. The synthesizer LLM only writes prose to match.

This was added after early versions showed ±15 points of grade drift across re-runs of the same repo.

### Validator/hydrator step

The synthesizer LLM produces JSON, but the JSON is run through `validator.validate_and_hydrate()` before reaching the user. Scanner-truth fields (file paths, line numbers, severity) are re-attached from the original findings. The LLM contributes prose only — it cannot tamper with citations.

### Themed 429s

The rate-limit response is part of the product, not an error message. Three sommelier-themed messages rotate based on a hash of the requester's IP. Cost ceiling (7 tastings/hour global) is enforced because Anthropic spend is the largest single risk to leaving this app running.

### tmpfs scratch + sweep on startup

Clones live in tmpfs (`/tmp/qs-work`, 1 GB cap from compose). On container restart, `_lifespan` calls `fetcher.sweep_work_root()` to delete any leftover dirs from a crashed worker. No cleanup cron, no disk pressure.

### In-browser JSX → built bundle

Started as `<script type="text/babel">`. Migrated to a one-step `esbuild` build in `build.mjs` once the JSX hit ~2 KLOC, mainly because PageSpeed flagged the in-browser transform on mobile. The build runs in the Dockerfile's first stage; production never executes Babel.

---

## Things this architecture explicitly does **not** do

- No persistent user data, no accounts, no auth.
- No PR scanning, no webhook integration, no GitHub App.
- No private repos.
- No multi-tenant rate limit (the global cap is by design).
- No retention beyond Celery's default result TTL.
- No autoscaling — single container, single host.
