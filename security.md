# Security

Quantum Sommelier ingests untrusted input (any public GitHub URL), executes `git clone` against it, runs deterministic AST analysis, and sends scanner-extracted snippets to a third-party LLM. This doc captures the threat model, controls, and known gaps.

---

## Threat model

### In scope

| Threat | Vector | Control |
|---|---|---|
| **Anthropic spend exhaustion** | Anyone hammering `POST /api/v1/tastings` to burn API credits | `QS_PER_IP_LIMIT=5/hr`, `QS_GLOBAL_LIMIT=7/hr` (slowapi, fixed-window in Redis). Global cap is the hard ceiling on hourly spend. |
| **Disk exhaustion via large clones** | Pasting a giant repo URL | Shallow clone (`--depth=1`), `QS_MAX_REPO_BYTES=500MB` cap, wall-clock timeout `QS_SCAN_TIMEOUT_S=120s`. Clones land in tmpfs (`/tmp/qs-work`, 1 GB hard cap from compose). |
| **Resource starvation via slow loris / hung clone** | Repos that stall mid-clone | Celery `task_time_limit` and `task_soft_time_limit` derived from `scan_timeout_s` (+30/+60s grace). `worker_max_tasks_per_child=25` limits memory creep. |
| **Repo-URL injection** | Crafted URLs that escape `git clone` arg parsing or hit non-GitHub hosts | `fetcher.normalize_repo_url()` parses + canonicalizes to `(owner, name)`; only `github.com` URLs accepted. Clone command uses an argv list, not a shell string. |
| **Unauthenticated GitHub rate limit** | Unauth API calls capped at 60/hr per IP | `GITHUB_TOKEN` (one or more comma-separated PATs in `token_pool.py`); rotated per-clone. PAT scope limited to `public_repo`. |
| **Cross-tenant leakage via tmpfs** | Clones from previous tastings remaining on disk | tmpfs scratch (auto-cleared on container restart) + `fetcher.cleanup()` in a `finally` block + `_lifespan` startup sweep of orphaned dirs. |
| **Bad LLM output reaching users** | Hallucinated CVE refs, fabricated file paths, schema-breaking content | Two-stage pipeline: judge votes on **scanner-extracted candidates only**; synthesizer never sees raw source. JSON-schema validation + `validator.validate_and_hydrate()` re-attaches scanner-truth fields after the LLM responds. |
| **Container reachability from the public internet** | Anyone hitting `:8080` directly | Prod compose override (`docker-compose.prod.yml`) binds to `127.0.0.1:8080` only. nginx on the host is the only inbound path. TLS via Let's Encrypt. |
| **Secret leakage via logs / errors** | API keys or PATs ending up in error messages | Settings frozen dataclass; secrets never serialized into responses. Pipeline-error responses cap detail at 400 chars and use a fixed themed message for the user-facing surface. |

### Out of scope

- Authenticated endpoints / user accounts (none exist).
- Private repos (clone path explicitly only takes public URLs).
- Webhook / PR-scanning integrations (none exist).
- Persistent multi-tenant storage (none exists).
- Defending against a determined attacker behind CGNAT who exhausts the global rate cap — by design, this just turns the app off for an hour.
- DDoS at the infrastructure layer — relies on AWS/CloudFront/upstream defenses.

---

## Secrets

| Secret | Where | Rotation |
|---|---|---|
| `ANTHROPIC_API_KEY` | `.env` on EC2 host, mounted via `env_file:` in compose | Manual; revoke + replace in Anthropic Console + redeploy. |
| `GITHUB_TOKEN` (PAT) | Same | PAT scope is `public_repo` only; rotation = create new PAT, append to env, redeploy, revoke old. |
| TLS private key | `/etc/letsencrypt/live/quantum-sommelier.charlesmorris.dev/` on host | `certbot renew` (cron). |
| EC2 SSH key | `~/.ssh/charlesworklaptoppersonal.pem` (operator's laptop) | Manual; replace by adding new pubkey to `~/.ssh/authorized_keys` on the box. |

`.env` is `.gitignore`d. `.env.example` ships placeholder values only. Never commit `.env`.

---

## Input validation

- `repo_url` body field is parsed by `normalize_repo_url()` — anything that doesn't reduce to `github.com/<owner>/<name>` is rejected with HTTP 400 (`invalid_url`).
- `ref` defaults to `"main"` and is passed to `git clone --branch`; not interpolated into a shell.
- `limit` on `/api/v1/trending` is an int; coerced by FastAPI.
- All POST/GET handlers use pydantic models (`backend/models.py`); FastAPI rejects malformed JSON before handlers run.

---

## Sandboxing

The clone + scan + LLM pipeline runs **inside the same container as the API**. The container runs as the default Python image user. There is no per-tasting subprocess sandbox or seccomp profile — defense-in-depth here relies on:

- Filesystem caps (tmpfs size limit, tmpfs is `/tmp/qs-work` only — host filesystem is read-only-ish for this process in practice).
- No network egress restrictions inside the container — but the only outbound calls are to `github.com` (clone) and `api.anthropic.com` (LLM).
- Time + byte caps on every clone.
- Celery worker recycles every 25 tasks (`worker_max_tasks_per_child=25`) to bound any leak.

This is acceptable for a public-repo-only scanner with no user data and a 7-tasting-per-hour ceiling. It would not be acceptable for a private-repo product.

---

## Rate limiting details

`backend/rate_limit.py` configures slowapi with Redis storage and fixed-window strategy:

- **Per-IP limit** — `5/hour`, keyed by client IP via `slowapi.util.get_remote_address`.
- **Global limit** — `7/hour`, shared across all IPs. Implemented via `limiter.shared_limit(scope="global_tastings")`.
- **Both limits stack** — request must pass both. Per-IP fires first.
- **Themed 429** — `themed_429()` returns one of three sommelier-themed messages, chosen by hashing the IP for stable cycling. Sets `Retry-After: 3600`.

Behind nginx, `slowapi` reads the IP from `X-Forwarded-For` if FastAPI's middleware sets it; otherwise falls back to remote address. Verify with `curl -H 'X-Forwarded-For: 1.2.3.4'` against staging if changing the proxy chain.

---

## Logging + observability

- Container logs to stdout/stderr → `docker logs quantum-sommelier`.
- No structured log shipping, no APM, no error reporter.
- No PII collected — IPs are kept only in slowapi's Redis bucket (TTL'd).
- Healthcheck: `GET /api/v1/health` every 30s (Docker `HEALTHCHECK`).

---

## Known gaps + accepted risks

| Gap | Why we accept it |
|---|---|
| No CSRF protection on `POST /api/v1/tastings` | Endpoint is rate-limited, idempotent in effect (creates a job), and not state-changing in any user-mutating way. |
| Open CORS (`allow_origins=["*"]`) | Single-origin deploy; no auth tokens; nothing to steal cross-origin. |
| No subprocess sandbox for `git clone` | Public-repo only, time/byte capped, tmpfs scratch. Adding bubblewrap/firejail/seccomp deferred until/unless the threat model expands. |
| No retention controls on Celery results | Default TTL applies; no PII; no enforced GDPR-style deletion because no user data. |
| Container runs as a non-root but non-hardened user | AL2023 host + nginx in front; defense-in-depth via host firewall + network ACLs is the primary control. |
| Single host, single container, no replication | Hobby-scale deploy. Spend cap (`QS_GLOBAL_LIMIT=7`) is the actual binding constraint, not capacity. |
| AI-generated config (Dockerfile, supervisord, nginx, Celery settings) | Reviewed by the operator before each deploy; failure modes are bounded by the time/byte caps above. |

---

## Reporting

Found something concerning? Email **colyermorris@gmail.com** with `[QS-SECURITY]` in the subject. There's no bug bounty — this is a portfolio project — but real reports get a real reply.
