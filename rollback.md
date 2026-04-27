# Rollback runbook — Quantum Sommelier

> **Audience:** a fresh Claude Code instance (or human) called in with no prior context, asked to roll the production deploy back to a previous good state.

This is meant to be self-contained. Read top to bottom before touching anything.

---

## 0. What you need before you start

Ask the user for:

- [ ] **EC2 host + SSH user** (e.g. `ec2-user@1.2.3.4`)
- [ ] **SSH key path** (e.g. `~/.ssh/<keyfile>.pem`)
- [ ] **What "rolled back to" means in this incident** — last known good tag? a commit SHA? "whatever was running 30 min ago"?

Do not run anything destructive until the user confirms the target state.

---

## 1. Where everything lives

| Thing | Location |
|---|---|
| Public URL | `https://quantum-sommelier.charlesmorris.dev` |
| Code on host | `/opt/quantum-sommelier/` |
| Compose files | `docker-compose.yml` + `docker-compose.prod.yml` (always pass both) |
| Container name | `quantum-sommelier` |
| Container port | `127.0.0.1:8080` (loopback only — nginx fronts it) |
| nginx vhost | `/etc/nginx/conf.d/quantum-sommelier.conf` (AL2023) or `/etc/nginx/sites-available/quantum-sommelier` (Ubuntu) |
| TLS cert | `/etc/letsencrypt/live/quantum-sommelier.charlesmorris.dev/` |
| Env file | `/opt/quantum-sommelier/.env` (mode 600, never in git) |
| Health endpoint | `http://127.0.0.1:8080/api/v1/health` (from host) |
| Public health | `https://quantum-sommelier.charlesmorris.dev/api/v1/health` |
| GitHub | `https://github.com/colyermorris/quantum-sommelier` |

The portfolio (`charlesmorris.dev` apex) runs in a separate stack on the same box. **Do not touch the apex's nginx blocks or containers.**

---

## 2. Triage first — is the container alive?

```bash
ssh -i <key> <user>@<host>
docker ps --filter name=quantum-sommelier
docker logs --tail 200 quantum-sommelier
curl -fsS http://127.0.0.1:8080/api/v1/health
```

If the container is up and healthy but the *site* is broken, the issue is probably nginx or the cert — not something a code rollback will fix. Check `sudo nginx -t`, `sudo journalctl -u nginx -n 100`, and the cert's expiry.

If the container is crashlooping or shipping bad responses, proceed to §3.

---

## 3. Roll back the container image

The deploy convention is to tag the running image **before** each new build, so rolling back is just retagging `:latest` and restarting.

### 3a. Find available tags

```bash
docker images quantum-sommelier --format 'table {{.Tag}}\t{{.CreatedAt}}\t{{.ID}}'
```

You should see something like:
```
TAG                CREATED AT
latest             2026-04-27 21:14:00 -0500
20260427-2110      2026-04-27 21:10:00 -0500
20260427-1530      2026-04-27 15:30:00 -0500
```

The non-`latest` tags are previous deploys. Pick the one the user wants.

> **If there are no dated tags, the deploy convention was skipped** — you can only roll back to whatever Docker still has cached. In that case skip to §4 (rebuild from a known-good git commit).

### 3b. Retag and restart

```bash
cd /opt/quantum-sommelier

# Save the currently-broken image so you can investigate later
docker tag quantum-sommelier:latest quantum-sommelier:broken-$(date +%Y%m%d-%H%M)

# Point :latest at the rollback target
docker tag quantum-sommelier:<target-tag> quantum-sommelier:latest

# Recreate the container against the new :latest
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Compose will see no Dockerfile change and just recreate from the (now-rolled-back) `:latest` image. Verify:

```bash
docker ps --filter name=quantum-sommelier
docker logs --tail 50 quantum-sommelier
curl -fsS http://127.0.0.1:8080/api/v1/health
```

Then from your laptop:

```bash
curl -fsS https://quantum-sommelier.charlesmorris.dev/api/v1/health
```

---

## 4. Fallback — rebuild from a known-good git commit

Use this if no usable image tag exists locally on the host.

```bash
# On the host
cd /opt/quantum-sommelier

# What's checked out right now? (this dir is rsynced, not git, so it may have no .git)
ls -la .git 2>/dev/null || echo "no .git in deploy dir — pull from GitHub instead"
```

The deploy dir is rsync'd from the laptop — it may not be a git checkout. Easiest path:

**Option A — re-rsync from a known-good local commit.** From the laptop:

```bash
git -C ~/Desktop/quantum-sommelier checkout <good-sha>
rsync -avz --delete \
  --exclude '.git' --exclude '.claude' --exclude '.env' \
  --exclude 'notes.md' --exclude '__pycache__' --exclude '.DS_Store' \
  -e "ssh -i <key>" \
  ~/Desktop/quantum-sommelier/ <user>@<host>:/opt/quantum-sommelier/
```

Then on the host:

```bash
cd /opt/quantum-sommelier
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**Option B — clone fresh on the host.** Slower but cleaner if the deploy dir is suspect:

```bash
ssh <user>@<host>
sudo mv /opt/quantum-sommelier /opt/quantum-sommelier.bad-$(date +%Y%m%d-%H%M)
sudo git clone https://github.com/colyermorris/quantum-sommelier.git /opt/quantum-sommelier
sudo git -C /opt/quantum-sommelier checkout <good-sha>
sudo cp /opt/quantum-sommelier.bad-*/. env /opt/quantum-sommelier/.env  # or scp from laptop
sudo chmod 600 /opt/quantum-sommelier/.env
cd /opt/quantum-sommelier
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 5. nginx-only rollback

If the breakage is in the nginx vhost, not the container:

```bash
# Backups should be alongside the live conf
sudo ls /etc/nginx/conf.d/ | grep quantum
# typically: quantum-sommelier.conf, plus *.bak files

sudo cp /etc/nginx/conf.d/quantum-sommelier.conf.bak \
        /etc/nginx/conf.d/quantum-sommelier.conf
sudo nginx -t && sudo systemctl reload nginx
```

If no `.bak` exists, the canonical config is in `deployment.md` §4 of this repo — copy it from there.

**Never restart nginx (`systemctl restart`) — always reload.** A restart drops the portfolio briefly too. `reload` is hot.

---

## 6. Stop everything (last resort)

If the rollback itself is misbehaving and the user wants the subdomain dark while the portfolio stays up:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
sudo mv /etc/nginx/conf.d/quantum-sommelier.conf /tmp/qs-nginx.conf.disabled
sudo nginx -t && sudo systemctl reload nginx
```

This takes the subdomain offline (visitors will get DNS-resolves-but-no-server). The portfolio is unaffected.

To bring it back: reverse both steps.

---

## 7. After any rollback

- [ ] Run the smoke tests from `deployment.md` §6 against the public URL
- [ ] `docker logs --tail 200 quantum-sommelier` — confirm no errors during startup
- [ ] Tell the user which image tag / commit SHA you ended on
- [ ] If you tagged a `:broken-*` image in §3b, leave it on the box for forensics — do not `docker rmi` it without confirmation

---

## 8. What NOT to do

- Don't `docker system prune` — it will wipe the rollback-tagged images you may need.
- Don't run `certbot renew` mid-rollback to "fix" something — renewals are scheduled, manual runs add a different failure mode.
- Don't edit `/opt/quantum-sommelier/.env` blindly. If the user thinks the rollback was caused by a bad env var, ask them to diff against their local copy first.
- Don't `git push --force` to the GitHub repo to "undo" a release. The remote is just a code mirror — production rolls back via image retag (§3) or rsync (§4), not by rewriting history.
- Don't touch the portfolio's nginx blocks or containers, even if "they look related." If unsure, ask.
