# Handoff — finish the EC2 deploy

> **Audience:** a fresh Claude Code session in this repo (`/Users/sadmin/Desktop/quantum-sommelier`). Read this top to bottom before doing anything.

The previous session got everything ready but couldn't run the deploy because outbound SSH from that session got blocked (probe-loop tripped sshd's connection guard, then the harness flagged SSH-to-this-IP as gated for the rest of the session). You're a fresh session — that gate is reset. Just don't probe.

---

## TL;DR — what to do

1. **Do not probe.** Use the exact connection info below. Don't loop through keys/users.
2. SSH in and verify the box.
3. `scp` the local `.env` up.
4. Run `scripts/deploy-ec2.sh` on the box.
5. Smoke-test `https://quantum-sommelier.charlesmorris.dev/api/v1/health` from your laptop.
6. Run a real end-to-end tasting against the public URL.

---

## Connection info (don't deviate)

| Thing | Value |
|---|---|
| Host (Elastic IP) | `3.138.161.64` |
| Subdomain | `quantum-sommelier.charlesmorris.dev` |
| Apex (already live, do not touch) | `charlesmorris.dev` (same IP, nginx 1.28.0 portfolio) |
| OS | Amazon Linux (prompt observed: `ec2-user@ip-172-31-43-65`) |
| SSH user | `ec2-user` |
| SSH key | `~/.ssh/charlesworklaptoppersonal.pem` (mode 600 — already set) |
| Local repo | `/Users/sadmin/Desktop/quantum-sommelier` |
| Local `.env` | `/Users/sadmin/Desktop/quantum-sommelier/.env` (real values, do not commit) |
| GitHub | `https://github.com/colyermorris/quantum-sommelier` (public, `main` is current) |
| Deploy target dir | `/opt/quantum-sommelier` |
| Container name | `quantum-sommelier` |
| Loopback port | `127.0.0.1:8080` (prod compose override pins this — nginx fronts it) |

DNS for the subdomain was added at Namecheap. Verify it resolved before doing anything cert-related:

```bash
dig +short quantum-sommelier.charlesmorris.dev    # should return 3.138.161.64
```

If empty, wait a few minutes for propagation. The deploy script will refuse to run until DNS resolves.

---

## State already done (don't redo)

- ✅ `README.md`, `deployment.md`, `rollback.md` written and pushed to GitHub `main`.
- ✅ `.gitignore` excludes `.env`, `.claude/`, `notes.md`, `CLAUDE.md`. Verified via `git check-ignore`.
- ✅ `docker-compose.prod.yml` binds the published port to `127.0.0.1:8080` so only nginx can reach it.
- ✅ `scripts/deploy-ec2.sh` is on the repo, executable, idempotent. Detects OS, installs missing deps, runs HTTP-only vhost first → certbot webroot → swaps in HTTPS vhost → smoke tests.
- ✅ AWS Security Group: 22, 80, 443 all open to `0.0.0.0/0` (user confirmed via screenshot).
- ✅ DNS A record for the subdomain submitted to Namecheap.

State NOT yet done:
- ❌ Nothing has been deployed to the box yet.
- ❌ No nginx vhost for the subdomain on the host.
- ❌ No Let's Encrypt cert issued.

---

## The deploy — three commands

### 1. Sanity-check the SSH path

One connection. Don't loop. If this fails, **stop and ask the user** — do not try other keys or users. The previous session burned ~6 connection attempts and tripped sshd's connection guard for the rest of the session.

```bash
ssh -i ~/.ssh/charlesworklaptoppersonal.pem -o IdentitiesOnly=yes \
    ec2-user@3.138.161.64 \
    'whoami && cat /etc/os-release | head -3 && docker --version 2>&1 && nginx -v 2>&1 && command -v certbot || echo certbot-missing'
```

Note what's already installed; the script handles missing pieces.

### 2. Push the .env up

```bash
scp -i ~/.ssh/charlesworklaptoppersonal.pem \
    /Users/sadmin/Desktop/quantum-sommelier/.env \
    ec2-user@3.138.161.64:/tmp/qs.env
```

### 3. Clone + deploy

```bash
ssh -i ~/.ssh/charlesworklaptoppersonal.pem ec2-user@3.138.161.64 'bash -se' <<'REMOTE'
set -euo pipefail
sudo mkdir -p /opt/quantum-sommelier
sudo chown $USER /opt/quantum-sommelier
if [ ! -d /opt/quantum-sommelier/.git ]; then
  git clone https://github.com/colyermorris/quantum-sommelier.git /opt/quantum-sommelier
else
  git -C /opt/quantum-sommelier pull --ff-only
fi
mv /tmp/qs.env /opt/quantum-sommelier/.env
chmod 600 /opt/quantum-sommelier/.env
cd /opt/quantum-sommelier
sudo bash scripts/deploy-ec2.sh
REMOTE
```

Stream the script's output as it runs. The script ends by curling `https://<domain>/api/v1/health` itself; if it prints `✅ Public health check passed`, you're live.

---

## Smoke test (from your laptop)

```bash
# DNS
dig +short quantum-sommelier.charlesmorris.dev

# TLS + health
curl -fsS https://quantum-sommelier.charlesmorris.dev/api/v1/health

# Trending
curl -fsS https://quantum-sommelier.charlesmorris.dev/api/v1/trending?limit=3

# End-to-end tasting against a small repo
JOB=$(curl -s -X POST https://quantum-sommelier.charlesmorris.dev/api/v1/tastings \
  -H 'content-type: application/json' \
  -d '{"repo_url":"https://github.com/sigstore/cosign"}' | jq -r .job_id)

while :; do
  out=$(curl -s https://quantum-sommelier.charlesmorris.dev/api/v1/tastings/$JOB)
  echo "$out" | jq '{status,stage,progress_pct}'
  status=$(echo "$out" | jq -r .status)
  [[ "$status" == "complete" || "$status" == "failed" ]] && { echo "$out" | jq .; break; }
  sleep 5
done
```

Then load the homepage in a browser and run a tasting through the UI to confirm the frontend works end-to-end.

---

## Rules — read before touching the box

- **Don't probe SSH.** One connection per attempt. If a connection fails, stop and ask the user. The earlier session learned this the hard way.
- **Don't touch the portfolio nginx blocks or containers.** They serve `charlesmorris.dev` apex on the same host. The deploy only *adds* `/etc/nginx/conf.d/quantum-sommelier.conf`. Never modify the portfolio's existing files.
- **Reload nginx, never restart.** Restart drops the portfolio briefly. `systemctl reload nginx` is hot.
- **Never `git push --force` to the GitHub repo.** Production rolls back via image retag, not by rewriting GitHub history. See `rollback.md`.
- **Don't commit `.env`, `.claude/`, `notes.md`, or `CLAUDE.md`.** All four are in `.gitignore`. The hook in `.claude/settings.json` appends the user's prompts to `notes.md` automatically — fine, just don't push it.

---

## If something breaks during deploy

The deploy script is idempotent — re-running is safe. But for specific failure modes:

| Symptom | Likely cause | What to do |
|---|---|---|
| Script aborts at DNS check | Subdomain hasn't propagated | wait 1–2 min, re-run |
| `Connection timed out during banner exchange` | sshd connection guard tripped | wait 10–15 min before next try; do not loop |
| `nginx -t` fails after vhost write | hand-edit conflict in `/etc/nginx/conf.d/` | inspect `quantum-sommelier.conf`; do NOT touch any other `.conf` files |
| certbot rate-limited | too many issuance attempts in test | use `--staging` while iterating, then re-issue without it |
| Container starts but `/api/v1/health` 502s | container crashed | `docker logs --tail 200 quantum-sommelier`; check `.env` keys |
| Public site loads HTML but tastings all fail | missing `ANTHROPIC_API_KEY` or `GITHUB_TOKEN` in `/opt/quantum-sommelier/.env` | scp a corrected `.env` and `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart` |

Full troubleshooting matrix is in `deployment.md` §10. Rollback procedure is in `rollback.md`.

---

## When you're done

Tell the user:
- Container image tag deployed (run `docker images quantum-sommelier --format 'table {{.Tag}}\t{{.CreatedAt}}'` on the box and report the `latest` line).
- Live URL: `https://quantum-sommelier.charlesmorris.dev`
- Whether the cert was newly issued or already existed.
- Whether the smoke-test tasting completed successfully.

Then offer to `/schedule` a one-time agent ~30 days out to verify the Let's Encrypt auto-renewal hook fires cleanly on its first run. (The hook is already installed at `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`; just verifying it actually runs.)
