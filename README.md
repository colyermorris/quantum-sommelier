# Quantum Sommelier

> A wine-tasting room for your codebase's post-quantum readiness.

Quantum Sommelier scans any public GitHub repository and serves up a **tasting note** — a structured, human-readable evaluation of how exposed it is to "harvest now, decrypt later" attacks and how prepared it is for the post-quantum migration. The verdict comes back as a letter grade, four sub-scores, an evidence-backed nose / palate / finish, and a shareable cork-card image.

Live: **https://quantum-sommelier.charlesmorris.dev**

---

## What it does

Paste any public GitHub URL. The pipeline:

1. **Fetches** a shallow clone of the repo (size & timeout bounded).
2. **Scans** the source for cryptographic primitives using tree-sitter parsers — symmetric ciphers, KEMs, signatures, hashes, TLS configs, JWT/JOSE algs, and PQ-specific markers (Kyber, Dilithium, Falcon, SPHINCS+, X25519MLKEM768, etc.).
3. **Scores** the project across four axes against a transparent rubric:
   - **HNDL exposure** — surface area for "harvest-now-decrypt-later" attacks.
   - **Signature agility** — ability to rotate or replace signature algorithms.
   - **Crypto hygiene** — general health of the cryptographic posture.
   - **PQ adoption readiness** — concrete post-quantum primitives already in use.
4. **Tastes** — Claude Haiku 4.5 turns the evidence into a sommelier-style note with nose, palate, finish, food pairings, and a cellar window estimate.
5. **Bottles** — a cork-shaped share card (PNG/SVG) is rendered server-side for posting.

The full rubric is exposed at `/api/v1/rubric` for transparency.

---

## Architecture

Single-container deploy. Runs three processes under `supervisord`:

| Process | Role |
|---|---|
| `redis` (loopback) | Celery broker + result backend |
| `uvicorn` | FastAPI app — REST API + static frontend |
| `celery worker` | Async tasting pipeline (clone → scan → score → LLM) |

```
┌──────────────────────────── container :8080 ───────────────────────────┐
│                                                                         │
│   FastAPI ──▶ Celery enqueue ──▶ Worker                                 │
│      │                            │                                     │
│      │                            ├─ git clone (shallow, bounded)       │
│      │                            ├─ tree-sitter scan                   │
│      │                            ├─ rubric scoring                     │
│      │                            ├─ Claude Haiku tasting note          │
│      │                            └─ resvg cork render                  │
│      │                                                                  │
│      └──▶ static frontend (Quantum Sommelier.html + JSX/CSS)            │
└─────────────────────────────────────────────────────────────────────────┘
```

The frontend is plain HTML + in-browser JSX (no build step). All API traffic is same-origin.

### Stack

- **Backend** — Python 3.12, FastAPI, Celery, Redis, slowapi, anthropic SDK
- **Scanner** — tree-sitter + tree-sitter-languages (Python/Go/JS/TS/Rust/Java/Ruby/C/C++ etc.)
- **LLM** — Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- **Cork render** — server-side SVG → PNG via `resvg-py`
- **Container** — Debian slim + supervisord; tmpfs scratch for clones

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness + scanner / rubric / model versions |
| `GET` | `/api/v1/rubric` | Full scoring rubric (axes, weights, thresholds) |
| `GET` | `/api/v1/trending?limit=5` | Curated rising GitHub repos |
| `POST` | `/api/v1/tastings` | Start a tasting — body: `{ "repo_url": "..." }` → `202` + `job_id` |
| `GET` | `/api/v1/tastings/{job_id}` | Poll status / fetch result |
| `GET` | `/api/v1/tastings/{job_id}/cork.png` | Cork share card (PNG) |
| `GET` | `/api/v1/tastings/{job_id}/cork.svg` | Cork share card (SVG) |

Rate limits (default): **5 tastings / hour / IP**, **100 / hour globally**. A themed 429 message is returned when the cellar is dry. Tunable via env.

---

## Local development

Prerequisites: Docker, an Anthropic API key, and a GitHub PAT (`public_repo` scope is enough — used to lift unauthenticated rate limits during clone + trending).

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY and GITHUB_TOKEN

docker compose up --build
# open http://localhost:8080
```

### Environment variables

See [`.env.example`](./.env.example). Key ones:

| Var | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | required |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | |
| `GITHUB_TOKEN` | — | required to avoid 60 req/hr unauth limit |
| `QS_PER_IP_LIMIT` | `5` | tastings/hour/IP |
| `QS_GLOBAL_LIMIT` | `100` | tastings/hour total |
| `QS_MAX_REPO_BYTES` | `524288000` | 500 MB clone cap |
| `QS_SCAN_TIMEOUT_S` | `120` | per-tasting wall clock |

---

## Deployment

Production lives on a shared EC2 host alongside the personal portfolio at charlesmorris.dev. nginx terminates TLS for the subdomain and reverse-proxies to the container on `127.0.0.1:8080`.

See [**deployment.md**](./deployment.md) for the full runbook — DNS, nginx vhost, Let's Encrypt, container bring-up, smoke tests, and rollback.

---

## Project layout

```
.
├── Quantum Sommelier.html      # entry HTML — bootstraps in-browser JSX
├── landing.jsx · scanning.jsx · tasting.jsx · overlays.jsx
├── styles*.css                 # tasting / cork / components styling
├── data.js                     # demo + content snippets
├── backend/
│   ├── main.py                 # FastAPI app + static frontend mount
│   ├── celery_app.py           # task queue + run_tasting task
│   ├── config.py               # env-driven Settings
│   ├── github/                 # url normalize, clone, trending
│   ├── scanner/                # tree-sitter rules, evidence collectors
│   ├── llm/                    # prompt templates + tasting pipeline
│   ├── cork/                   # SVG cork render → PNG
│   ├── rate_limit.py           # slowapi limiter + themed 429
│   └── models.py               # pydantic schemas
├── Dockerfile                  # single-container build
├── docker-compose.yml          # dev (publishes 0.0.0.0:8080)
├── docker-compose.prod.yml     # prod override — binds to 127.0.0.1:8080
├── supervisord.conf            # redis + api + worker
└── deployment.md               # production runbook
```

---

## License

MIT.
