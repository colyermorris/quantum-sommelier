# Deployment — Quantum Sommelier

Target: ride along on the existing **charlesmorris.dev** EC2 host as a separate subdomain.

- **Public URL:** `https://quantum-sommelier.charlesmorris.dev`
- **Container port:** `8080` (loopback only in prod)
- **Fronted by:** existing host nginx (TLS termination + reverse proxy)
- **Coexistence:** the portfolio's vhosts on `:80/:443` are untouched. We add one new server block.
- **Portfolio entry:** listed on `https://charlesmorris.dev/projects` — entry is hardcoded in `/var/www/charlesmorris.dev/site/src/pages/Projects.tsx` (Vite + React + TS). After editing, run `npm run build` in that dir and atomically swap `dist/` into `/var/www/charlesmorris.dev/html/`.

## Host facts (for next time)

| Thing | Value |
|---|---|
| EC2 Elastic IP | `3.138.161.64` |
| Instance | `i-01b43706fd019b258` (us-east-2c, AL2023) |
| SSH user / key | `ec2-user` / `~/.ssh/charlesworklaptoppersonal.pem` |
| SG inbound | 22, 80, 443, 5173 — all `0.0.0.0/0` |
| Security group | `sg-0bbb19fa922ed4053` (launch-wizard-3) |
| Portfolio root | `/var/www/charlesmorris.dev/html/` (built bundle); source in `…/site/` |
| Portfolio nginx | `/etc/nginx/conf.d/charlesmorris.dev.conf` (do not edit) |
| QS deploy dir | `/opt/quantum-sommelier/` |
| QS nginx | `/etc/nginx/conf.d/quantum-sommelier.conf` (managed by `scripts/deploy-ec2.sh`) |
| QS cert | `/etc/letsencrypt/live/quantum-sommelier.charlesmorris.dev/` |

---

## 0. Before you start — what I need from you

Drop these in chat and I can run the deploy end-to-end:

- [ ] **EC2 public IP or hostname** (or a DNS name that already resolves to it)
- [ ] **SSH login user** (typically `ec2-user` for AL2023 / `ubuntu` for Ubuntu)
- [ ] **SSH private key** — drop a new `.pem` into `~/.ssh/` and give me the filename
- [ ] **Confirm DNS provider** so we know where to add the A/CNAME record
- [ ] **Confirm Docker & nginx are already installed on the host** (true if the portfolio is live)

---

## 1. DNS

Add **one** record at the provider for `charlesmorris.dev`:

| Type | Name | Value | TTL |
|---|---|---|---|
| `A` | `quantum-sommelier` | `<EC2 public IP>` | `300` |

If the apex is fronted by Cloudflare/Netlify/etc., use the EC2 IP directly here — we do not want the proxy in front of this subdomain because we're terminating TLS ourselves with Let's Encrypt on the box.

Wait until `dig +short quantum-sommelier.charlesmorris.dev` returns the IP before issuing the cert.

---

## 2. Ship the code to the host

From your laptop, in this repo:

```bash
# one-shot rsync (skips git history, .env, .claude, scratch dirs)
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.claude' \
  --exclude '.env' \
  --exclude 'notes.md' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  -e "ssh -i ~/.ssh/<keyfile>.pem" \
  ./ <user>@<host>:/opt/quantum-sommelier/
```

Then SCP your filled-in `.env` separately so it never lands in any git or rsync mirror:

```bash
scp -i ~/.ssh/<keyfile>.pem .env <user>@<host>:/opt/quantum-sommelier/.env
ssh -i ~/.ssh/<keyfile>.pem <user>@<host> 'chmod 600 /opt/quantum-sommelier/.env'
```

> **Why rsync, not git pull:** the host should not need a GitHub deploy key, and the `.env` lives only on the box.

---

## 3. Build & start the container

SSH in:

```bash
ssh -i ~/.ssh/<keyfile>.pem <user>@<host>
cd /opt/quantum-sommelier

docker compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  up -d --build
```

The prod override binds the published port to `127.0.0.1:8080` so it is **not** reachable from the public internet directly — only via nginx.

Health check:

```bash
curl -fsS http://127.0.0.1:8080/api/v1/health
# → {"status":"ok",...}
```

Tail logs:

```bash
docker logs -f quantum-sommelier
```

---

## 4. nginx server block

Drop this into `/etc/nginx/conf.d/quantum-sommelier.conf` (Amazon Linux) or `/etc/nginx/sites-available/quantum-sommelier` + symlink into `sites-enabled/` (Ubuntu).

```nginx
# HTTP — for ACME challenge + redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name quantum-sommelier.charlesmorris.dev;

    # Let certbot handle .well-known/acme-challenge/ via webroot
    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS — TLS termination + reverse proxy to container
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name quantum-sommelier.charlesmorris.dev;

    ssl_certificate     /etc/letsencrypt/live/quantum-sommelier.charlesmorris.dev/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/quantum-sommelier.charlesmorris.dev/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # The cork PNG/SVG endpoints are tiny; tasting bodies are small JSON.
    # Bump if you ever attach larger uploads.
    client_max_body_size 2m;

    # Long-poll friendly — tastings can take 60-120s end to end.
    proxy_read_timeout 180s;
    proxy_send_timeout 180s;

    # Pass real client IP to slowapi for per-IP rate limits.
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP       $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host             $host;

    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}
```

Validate + reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> **Why the order:** the HTTP-only server must exist *before* certbot runs in webroot mode, but we leave the HTTPS block listed even before the cert exists — `nginx -t` will fail until the cert is issued. Easiest path: start with the HTTPS block commented out, run certbot (step 5), then uncomment + reload.

---

## 5. Let's Encrypt

Use webroot mode so renewal does not need to stop nginx (the portfolio stays up). Make sure the webroot exists:

```bash
sudo mkdir -p /var/www/letsencrypt
```

Issue the cert (Amazon Linux):

```bash
sudo certbot certonly --webroot \
  -w /var/www/letsencrypt \
  -d quantum-sommelier.charlesmorris.dev \
  --non-interactive --agree-tos -m colyermorris@gmail.com
```

Auto-renew is already on if the box has the `certbot.timer` (systemd) or the cron drop-in. Verify:

```bash
sudo systemctl list-timers | grep certbot
# or
cat /etc/cron.d/certbot
```

Reload nginx after each renewal:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

---

## 6. Smoke tests

From your laptop:

```bash
# DNS
dig +short quantum-sommelier.charlesmorris.dev

# TLS + health
curl -fsS https://quantum-sommelier.charlesmorris.dev/api/v1/health

# Trending
curl -fsS https://quantum-sommelier.charlesmorris.dev/api/v1/trending?limit=3

# End-to-end tasting (poll until status == complete)
JOB=$(curl -s -X POST https://quantum-sommelier.charlesmorris.dev/api/v1/tastings \
  -H 'content-type: application/json' \
  -d '{"repo_url":"https://github.com/openssl/openssl"}' | jq -r .job_id)

watch -n 3 "curl -s https://quantum-sommelier.charlesmorris.dev/api/v1/tastings/$JOB | jq .status,.stage,.progress_pct"
```

And in a browser: load the homepage, paste any public GitHub URL, watch it run.

---

## 7. Updating after the first deploy

For UI / backend changes:

```bash
# from laptop
rsync -avz --delete --exclude '.git' --exclude '.claude' --exclude '.env' \
  --exclude 'notes.md' --exclude '__pycache__' --exclude '.DS_Store' \
  -e "ssh -i ~/.ssh/<keyfile>.pem" \
  ./ <user>@<host>:/opt/quantum-sommelier/

# on host
cd /opt/quantum-sommelier
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Frontend-only edits do **not** need a rebuild — `Quantum Sommelier.html` and the `.jsx`/`.css` files are baked into the image at build time, so a code change does require a rebuild. If you want hot iteration without a rebuild, mount `./` into `/app/frontend` via an additional compose override; not done by default to keep prod immutable.

---

## 8. Rollback

```bash
# Tag before each deploy
docker tag quantum-sommelier:latest quantum-sommelier:$(date +%Y%m%d-%H%M)

# Roll back
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker tag quantum-sommelier:<previous-tag> quantum-sommelier:latest
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 9. Operational notes

- **Scratch dir:** `/tmp/qs-work` inside the container is `tmpfs` (1 GB cap), so crashed clones cannot fill the host disk.
- **Memory:** the worker is `--concurrency=2` and `--pool=prefork`; expect ~400 MB per running tasting plus baseline ~250 MB. Fine on a `t3.small` if the portfolio is the only neighbor.
- **Logs:** all three processes log to stdout/stderr and end up in `docker logs quantum-sommelier`. No log rotation in-container — Docker's json-file driver handles it.
- **Keys / quotas:** the Anthropic key is per-tasting Haiku spend; the GitHub PAT only does read clones + trending. Both live in `/opt/quantum-sommelier/.env` and never leave the box.
- **Rate limits:** in-process via `slowapi`; restarting the container resets the bucket. Acceptable for portfolio scale.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `502 Bad Gateway` | container not up or crashed | `docker ps`, `docker logs quantum-sommelier`, `curl http://127.0.0.1:8080/api/v1/health` |
| `nginx: [emerg] cannot load certificate` | running HTTPS block before cert issued | comment out the `443` server block, reload, run certbot, uncomment, reload |
| Tasting stuck at `queued` | celery worker not running inside container | `docker exec quantum-sommelier supervisorctl status` — restart `worker` |
| `request failed` from frontend on every URL | missing/invalid `GITHUB_TOKEN` or hit GitHub 60/hr unauth limit | check `.env`, `docker logs` for `GitHubError` |
| All tastings return generic LLM text | missing/invalid `ANTHROPIC_API_KEY` | check `.env`, watch logs for `AnthropicError` |
| Cork PNG looks like SVG / wrong content-type | `resvg-py` failed silently — fonts missing | rebuild image (Dockerfile installs `fonts-dejavu-core` + `fonts-liberation`) |
| Cert renewal silently fails | webroot path mismatch with nginx config | confirm `/var/www/letsencrypt` exists and the HTTP server block points at it |
| `docker compose ... unknown shorthand flag: 'f'` after fresh AL2023 docker install | AL2023 has no `docker-compose-plugin` rpm — Compose v2 plugin must be installed manually | `scripts/deploy-ec2.sh` now drops the official static binary into `/usr/local/lib/docker/cli-plugins/docker-compose`; re-run the script |
| `certbot: No such authorization` on first issuance | stale ACME account state from a prior partial run on this box (no certs present locally) | re-run `certbot certonly --webroot -w /var/www/letsencrypt -d <domain> --non-interactive --agree-tos -m <email>` once and the script will pick the cert up on the next pass |
| SSH `Connection timed out during banner exchange` from a campus / restrictive network | the upstream network (e.g. UNCC Wi-Fi) is dropping outbound port 22, not the EC2 box | verify off-network: `nc -vz 3.138.161.64 22`. If it works off-campus, the issue is your network, not sshd. AL2023's sshd shows `MaxStartups`-throttle entries but those self-clear in ~6 min |
