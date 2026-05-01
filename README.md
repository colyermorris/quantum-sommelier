# Quantum Sommelier

> A wine-tasting room for your codebase's post-quantum readiness.

## Project title & overview

**Quantum Sommelier** scans any public GitHub repository and serves up a **tasting note** — a structured, human-readable evaluation of how exposed the codebase is to "harvest now, decrypt later" (HNDL) attacks and how prepared it is for the post-quantum migration.

Paste a GitHub URL → get back a letter grade, four sub-scores (HNDL exposure, signature agility, crypto hygiene, PQ adoption readiness), an evidence-backed nose / palate / finish written in sommelier prose, a food + compliance pairing, and a shareable cork-card PNG/SVG.

Live: **https://quantum-sommelier.charlesmorris.dev**

The product framing is deliberate: post-quantum cryptography is a niche topic that most engineers tune out. Wrapping a real scanner in wine-tasting language makes the rubric memorable, the share card postable, and the scoring transparent (`/api/v1/rubric` exposes the full rubric). The engineering underneath is a tree-sitter AST scanner with an LLM judge stage and a deterministic numeric scorer — the LLM contributes prose, never a grade.

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

## Architecture summary

Single-container deploy on one EC2 host, fronted by nginx (TLS via Let's Encrypt). The container runs three processes under `supervisord`. The pipeline is **AST-first, LLM-second** — tree-sitter extracts crypto findings from source; Claude Haiku 4.5 judges those findings to drop false positives, then synthesizes the prose; a deterministic scorer computes the numeric grade so the LLM cannot drift it.

Full system design — process layout, data flow, deploy topology, design decisions — lives in [**architecture.md**](./architecture.md).

Threat model, rate limits, secrets handling, and known gaps live in [**security.md**](./security.md).

### Quick view

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
- **Frontend** — React 18 JSX, esbuild bundle, plain CSS (no framework)

---

## AI models and tools used

This project was scoped, designed, built, and deployed primarily through AI tools. Each one had a distinct role.

| Tool | Where | Role |
|---|---|---|
| **Claude Code** (Opus 4.6 / 4.7, 1M context) | Local dev loop in this repo | Primary engineering agent. Wrote ~all of the backend (FastAPI, Celery, tree-sitter scanner, LLM pipeline, cork renderer), the frontend (in-browser JSX → esbuild bundle), Dockerfile, supervisord config, EC2 deploy/rollback scripts, and most of the docs. Iterative back-and-forth driven by screenshots and PageSpeed PDFs. |
| **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) | Runtime, inside the container | Two LLM stages in the tasting pipeline: **judge** (`backend/llm/judge.py`) — votes confirm/drop on each scanner candidate to filter false positives — and **synthesizer** (`backend/llm/synthesizer.py`) — turns confirmed findings + score into nose/palate/finish/pairing prose. Both calls are JSON-schema-constrained and validated/hydrated before reaching users. |
| **Claude.ai (web)** | Off-repo, before/around dev | Initial PRD scoping, the wine-sommelier metaphor + rubric brainstorm, and the design-system handoff (the original `Quantum Sommelier.html` shell came from `api.anthropic.com/v1/design/...`). Used as a sounding board for "is this the right shape" questions before opening Claude Code. |
| **Grok** | Off-repo | Cross-checked the post-quantum cryptography rubric (HNDL exposure, signature agility, PQ adoption readiness) and sanity-checked claims about Kyber / Dilithium / X25519MLKEM768 hybrids. Second opinion when one model felt like it was confabulating. |
| **GitHub API** | Runtime + dev | Trending repos, shallow clone fetch, rotating PAT pool. Not an AI tool, but the trending strip is the input AI can't fabricate. |
| **tree-sitter / tree-sitter-languages** | Runtime, in `backend/scanner/` | Deterministic AST parsing across 9 languages. Listed here because the architecture is deliberately **AST-first, LLM-second** — the LLM never sees raw repo content, it only judges what tree-sitter already extracted. This is what stops hallucinated findings. |

The runtime chain: `tree-sitter scan → Haiku judge (drop false positives) → deterministic scorer (rubric weights) → Haiku synthesizer (prose) → validator (re-attach scanner-truth fields, refuse hallucinated CVEs) → tasting note`.

---

## AI engineering analysis

### Strengths and limitations of the AI tools used

**Strengths**

- **Claude Code at iterative UI work.** Pasting a screenshot of a layout bug + a one-line description produced a correct CSS fix in 1–2 turns most of the time. Mobile spacing, cork-card overflow, header bar widths — all driven this way.
- **Domain knowledge bootstrap.** Post-quantum crypto vocabulary (Kyber, Dilithium, SPHINCS+, X25519MLKEM768, JOSE alg edge cases) was generated reliably enough to seed a plausible rubric without a domain expert in the room. Cross-checking with Grok caught a couple of confidently-wrong claims.
- **Structured-output reliability with JSON schemas.** Constraining Haiku to a strict JSON shape and running output through a validator made the LLM stages safe to put behind a public endpoint. The synthesizer cannot invent a finding because it never sees the source — it only sees scanner-extracted candidates.
- **Speed of plumbing.** Dockerfile multi-stage build, supervisord conf, nginx reverse-proxy vhost, certbot setup, deploy + rollback scripts — all bootstrapped in minutes from prompts.

**Limitations**

- **Confident wrong answers in unfamiliar territory.** The first EC2 deploy hung on SSH connection drops. Claude Code generated detailed `iptables` / `fail2ban` / `MaxStartups` advice that was all irrelevant — the actual cause was UNC Charlotte's campus network blocking outbound port 22. Cost ~30 minutes.
- **Over-engineering by default.** Without scope guards, Claude Code will create extra files (`handoff.md`, `rollback.md`, multiple split CSS files), add backwards-compat shims, and write docstrings nobody asked for. Required an explicit scope-discipline rule in `CLAUDE.md`.
- **Subtle multi-file inconsistencies.** Changes that touched both code and docs (e.g. updating rubric thresholds) sometimes landed in only one place. Required deliberate "now grep for the old value everywhere" turns.
- **UI fragility from multi-turn iteration.** Several rounds of "fix this layout" without re-stating the full layout intent caused churn — fixing one breakpoint broke another. Mitigated by introducing `styles-mobile.css` and PageSpeed-driven verification.
- **Vibe-debugging without a reproduction.** "Fix the cork card" without a screenshot of *which* failure mode (cropped vs. blank vs. corrupted PNG) traded one bug for another. Always include the artifact.

### Tradeoffs encountered

- **Single container vs. multi-service compose.** Picked single-container + supervisord because the deploy target is one EC2 box already running another app. Trade: harder to scale individual processes; easier to operate at this size.
- **Haiku 4.5 over Opus / Sonnet.** Haiku is ~10–20× cheaper per tasting and fast enough that the rate cap (7/hour global) is the real bottleneck, not latency. Trade: weaker reasoning on edge cases — mitigated by the deterministic scorer doing the actual numeric scoring.
- **AST-first scanner over LLM-only.** Trade: every supported language needs explicit tree-sitter rules. Pays off in correctness — there is a real grammar between the LLM and the user.
- **In-browser JSX → built bundle.** Easy dev loop early; had to migrate to a one-step esbuild build before deploy because PageSpeed flagged the in-browser Babel transform on mobile.
- **Open CORS + IP-keyed rate limit.** Simplest correct thing for a single-origin deploy. Trade: a determined attacker behind CGNAT can starve the global cap. Acceptable for this project's threat model (see [`security.md`](./security.md)).

### Prompting strategies that worked (and failed)

**Worked**

- **Two-stage scan → judge → synthesize.** Giving the synthesizer the raw scan produced flowery but inaccurate notes (made-up algorithms, hallucinated CVEs). Splitting into a *judge* that only votes on candidates the deterministic scanner already found, then passing **only confirmed findings** to the synthesizer, eliminated almost all hallucination.
- **Strict JSON schemas + a validator/hydrator step.** Both LLM calls are forced into a JSON shape. `backend/llm/validator.py` re-attaches scanner-truth fields (file paths, line numbers, severity) so the LLM can't tamper with citations. The LLM contributes prose only.
- **Screenshots > prose for UI bugs.** Pasting cropped screenshots into Claude Code produced fixes in 1–2 turns. Describing the same bug in words took 3–5.
- **PRD-style upfront framing.** The first real prompt asked for a "full PRD" before any code. Most architectural decisions (single container, supervisord, Celery + Redis loopback, tmpfs scratch) flow from that PRD and didn't need re-litigating later.
- **Auto-memory + a verbatim prompt log.** `notes.md` (the verbatim log) plus auto-memory (`memory/host_layout.md`, `memory/deploy_gotchas.md`) made cold-start sessions productive without re-deriving context. `handoff.md` glued the gap during one cross-session deploy.

**Failed**

- **Free-text LLM scoring.** First synthesizer drafts let the model "feel out" a grade. It drifted by ±15 points across re-runs of the same repo. Fix: deterministic scorer (`backend/llm/scorer.py`) computes the numeric score from rubric weights; the LLM only writes prose to match.
- **Vibe-debugging the EC2 SSH issue.** AI happily generated 30+ minutes of wrong fixes for a network-egress problem before the user spotted the campus-network constraint.
- **Letting Claude Code create extra files unprompted.** Several docs/files were generated without a clear ask. Now governed by an explicit scope rule.
- **"Fix and improve" prompts without a reproduction.** Caused regressions.

---

## Engineering reflection

### What I would do differently without AI

A reasonable "no-AI" version of this project would have been: one language (probably Go), regex-based crypto detection, a numeric score, no narrative output, no cork share card, no themed 429 messages. Estimated **4–6× longer** to a comparable feature set, and the resulting product would have been much less interesting to look at — the sommelier framing depends on prose generation that's tedious to write by hand for every scoring outcome. I'd also have skipped most of the language coverage; tree-sitter rules across nine languages is realistic with AI bootstrapping and unrealistic on a one-person evening-and-weekend timeline without it.

I'd have chosen a more conventional shape: probably a CLI scanner that prints a numeric report, with an optional `--json` flag, and no web UI at all. The cork share card and the sommelier metaphor exist *because* AI made narrative generation cheap.

### What AI improved vs. degraded

**Improved**

- **Surface-area coverage.** Tree-sitter rules across 9 languages got drafted in hours, not weeks.
- **Domain knowledge.** Post-quantum cryptography is niche; AI brought enough vocabulary to bootstrap a plausible rubric without a domain expert.
- **UI iteration speed.** Screenshot-driven CSS fixes are AI's sweet spot — most mobile and cork-card layout passes were 1–2 turn fixes.
- **Deployment plumbing.** Supervisord, multi-stage Dockerfile, nginx vhost, certbot, deploy/rollback scripts all bootstrapped from prompts.
- **Narrative output.** The sommelier prose is the product; without a runtime LLM there is no product.

**Degraded**

- **Time spent on confident-wrong answers.** Most painfully, the EC2 SSH debug session — but smaller versions of this happened often (e.g. AI-suggested config flags that didn't exist, library APIs that had changed).
- **Diff churn.** Multi-turn iteration on the same file produced more revert-the-revert moments than a single careful pass would have. Required a "scope discipline" rule to claw back.
- **Subtle drift across files.** Doc/code mismatches snuck in when a change touched both. AI is fast at writing changes and slow at noticing what else needs updating.
- **A bias toward generating new files.** Several files were created that should have been edits. Eventually mitigated by the rule "default to editing existing files."

Net: the project shipped roughly an order of magnitude faster than it would have without AI, with better surface coverage and a more interesting product, at the cost of needing explicit guardrails (the scope rule, the prompt log, the validator step) to stop AI's failure modes from leaking into production.

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

## Supporting context files

Structured documents referenced by this README and used to guide AI work in this repo:

- [`architecture.md`](./architecture.md) — system design, data flow, process layout, deploy topology, design decisions.
- [`security.md`](./security.md) — threat model, rate limits, secrets handling, sandboxing, known gaps.
- [`CLAUDE.md`](./CLAUDE.md) — model interaction notes + project rules Claude Code follows in this repo (prompt log, scope discipline, deploy rules).
- [`deployment.md`](./deployment.md) — production runbook (DNS, nginx, certbot, container bring-up, smoke tests, rollback).
- [`rollback.md`](./rollback.md) — cold-start recovery instructions for handing off to a fresh Claude Code session.
- [`handoff.md`](./handoff.md) — context dump used when handing off to a new session mid-deploy.
- [`notes.md`](./notes.md) — verbatim prompt log (every user turn, in order, timestamped). Maintained automatically by a `UserPromptSubmit` hook in `.claude/settings.json`.
- `.claude/` — Claude Code settings, hooks, and project-scoped permissions.
- `~/.claude/projects/-Users-sadmin-Desktop-quantum-sommelier/memory/` — auto-memory captured across sessions (host layout, deploy gotchas).

---

## License

MIT.
