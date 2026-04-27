#!/usr/bin/env bash
# Quantum Sommelier — one-shot deploy script for the charlesmorris.dev EC2 box.
#
# Idempotent. Re-run as many times as you like.
#
# Pre-reqs:
#   - You're on the EC2 box (Amazon Linux 2023 expected; Ubuntu also handled).
#   - You've cloned the repo to /opt/quantum-sommelier (or wherever — script auto-detects via $PWD).
#   - You've placed the production .env at $REPO_ROOT/.env (mode 600).
#   - DNS for $DOMAIN already resolves to this box's public IP.
#   - Existing portfolio on this host is untouched. We only ADD one nginx server block.
#
# Usage:
#   sudo bash scripts/deploy-ec2.sh
#
set -euo pipefail

DOMAIN="quantum-sommelier.charlesmorris.dev"
EMAIL="colyermorris@gmail.com"
CONTAINER_NAME="quantum-sommelier"
LOOPBACK_PORT=8080
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
NGINX_CONF_NAME="quantum-sommelier.conf"
WEBROOT="/var/www/letsencrypt"

log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m  %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[err]\033[0m   %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || err "Run with sudo: sudo bash scripts/deploy-ec2.sh"

# ── 1. Detect OS / package manager ──────────────────────────────
if [[ -f /etc/os-release ]]; then . /etc/os-release; fi
OS_ID="${ID:-unknown}"
log "OS detected: $OS_ID ${VERSION_ID:-}"

case "$OS_ID" in
  amzn|rhel|centos|fedora) PKG=yum; NGINX_CONFD=/etc/nginx/conf.d ;;
  ubuntu|debian)           PKG=apt; NGINX_CONFD=/etc/nginx/conf.d ;;
  *) err "Unsupported OS: $OS_ID — extend this script if needed" ;;
esac

apt_install() { DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"; }
yum_install() { yum install -y "$@"; }
pkg_install() { if [[ $PKG == apt ]]; then apt_install "$@"; else yum_install "$@"; fi; }

if [[ $PKG == apt ]]; then apt-get update -y >/dev/null; fi

# ── 2. Pre-flight ───────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || err ".env missing at $ENV_FILE — scp it from your laptop first (chmod 600)"
chmod 600 "$ENV_FILE" || true

log "Checking DNS for $DOMAIN ..."
if command -v dig >/dev/null; then
  RESOLVED=$(dig +short "$DOMAIN" | tail -n1)
else
  RESOLVED=$(getent hosts "$DOMAIN" | awk '{print $1}' | tail -n1)
fi
HOST_IP=$(curl -fsS https://api.ipify.org || echo "")
if [[ -z "$RESOLVED" ]]; then
  warn "DNS for $DOMAIN does not resolve yet."
  warn "Add an A record: $DOMAIN -> $HOST_IP and re-run."
  err  "Aborting before any nginx/cert work."
fi
log "DNS resolves to $RESOLVED (this box: $HOST_IP)"
[[ "$RESOLVED" == "$HOST_IP" ]] || warn "DNS resolves elsewhere — proceeding anyway, but TLS issuance will fail if mismatched."

# ── 3. Ensure docker is installed + running ─────────────────────
if ! command -v docker >/dev/null; then
  log "Installing Docker ..."
  if [[ $PKG == yum ]]; then
    yum_install docker
    systemctl enable --now docker
    usermod -aG docker ec2-user || true
  else
    apt_install ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt_install docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    usermod -aG docker ubuntu || true
  fi
else
  log "Docker present: $(docker --version)"
fi

# Compose v2 plugin sanity
docker compose version >/dev/null 2>&1 || {
  log "Installing docker compose v2 plugin ..."
  if [[ $PKG == yum ]]; then yum_install docker-compose-plugin || true; fi
}

# ── 4. Ensure nginx + certbot are installed ─────────────────────
if ! command -v nginx >/dev/null; then
  log "Installing nginx ..."
  pkg_install nginx
  systemctl enable --now nginx
else
  log "nginx present: $(nginx -v 2>&1)"
fi

if ! command -v certbot >/dev/null; then
  log "Installing certbot ..."
  if [[ $PKG == yum ]]; then
    yum_install certbot python3-certbot-nginx || yum_install certbot
  else
    apt_install certbot python3-certbot-nginx
  fi
else
  log "certbot present: $(certbot --version 2>&1)"
fi

mkdir -p "$WEBROOT"
chown -R nginx:nginx "$WEBROOT" 2>/dev/null || chown -R www-data:www-data "$WEBROOT" 2>/dev/null || true

# ── 5. Tag the previous image (if any) for rollback ─────────────
if docker image inspect "$CONTAINER_NAME:latest" >/dev/null 2>&1; then
  TAG="rollback-$(date +%Y%m%d-%H%M%S)"
  log "Tagging current $CONTAINER_NAME:latest as $CONTAINER_NAME:$TAG"
  docker tag "$CONTAINER_NAME:latest" "$CONTAINER_NAME:$TAG"
fi

# ── 6. Build + start the container ──────────────────────────────
cd "$REPO_ROOT"
log "Building + starting container ..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

log "Waiting for container to report healthy on 127.0.0.1:$LOOPBACK_PORT ..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$LOOPBACK_PORT/api/v1/health" >/dev/null 2>&1; then
    log "Container healthy after ${i}s."
    break
  fi
  sleep 2
  [[ $i -eq 30 ]] && { docker logs --tail 100 "$CONTAINER_NAME"; err "Container failed to come up healthy in 60s"; }
done

# ── 7. Stage 1 nginx vhost — HTTP only (for ACME challenge) ─────
HTTP_ONLY_CONF="/tmp/${NGINX_CONF_NAME}.http"
cat >"$HTTP_ONLY_CONF" <<EOF
# Quantum Sommelier — managed by deploy-ec2.sh — DO NOT EDIT BY HAND
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root $WEBROOT;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

INSTALLED_CONF="$NGINX_CONFD/$NGINX_CONF_NAME"

# Only swap the live config if certs are not yet present.
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if [[ ! -f "$CERT_PATH" ]]; then
  log "No cert yet — installing HTTP-only vhost so certbot webroot can run."
  cp "$HTTP_ONLY_CONF" "$INSTALLED_CONF"
  nginx -t
  systemctl reload nginx

  log "Issuing Let's Encrypt cert for $DOMAIN ..."
  certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos -m "$EMAIL" --keep-until-expiring
fi

# ── 8. Stage 2 nginx vhost — HTTPS reverse proxy ────────────────
FINAL_CONF="/tmp/${NGINX_CONF_NAME}.final"
cat >"$FINAL_CONF" <<EOF
# Quantum Sommelier — managed by deploy-ec2.sh — DO NOT EDIT BY HAND
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root $WEBROOT;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 2m;

    proxy_read_timeout 180s;
    proxy_send_timeout 180s;

    proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP         \$remote_addr;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Host              \$host;

    location / {
        proxy_pass http://127.0.0.1:$LOOPBACK_PORT;
    }
}
EOF

# Only overwrite if changed (avoid pointless reloads)
if ! cmp -s "$FINAL_CONF" "$INSTALLED_CONF" 2>/dev/null; then
  log "Writing final nginx vhost to $INSTALLED_CONF"
  cp "$FINAL_CONF" "$INSTALLED_CONF"
  nginx -t
  systemctl reload nginx
else
  log "nginx vhost already up-to-date."
fi

# ── 9. Renewal hook — reload nginx after each cert renewal ──────
HOOK_DIR=/etc/letsencrypt/renewal-hooks/deploy
HOOK_FILE="$HOOK_DIR/reload-nginx.sh"
mkdir -p "$HOOK_DIR"
if [[ ! -f "$HOOK_FILE" ]]; then
  log "Installing nginx reload hook for cert renewals."
  cat >"$HOOK_FILE" <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
  chmod +x "$HOOK_FILE"
fi

# ── 10. Smoke test the public URL ───────────────────────────────
log "Smoke testing https://$DOMAIN/api/v1/health ..."
sleep 2
if curl -fsS "https://$DOMAIN/api/v1/health" | tee /dev/stderr | grep -q '"status":"ok"'; then
  log "✅ Public health check passed."
else
  warn "Public health check did not return ok. Check 'docker logs $CONTAINER_NAME' and 'sudo nginx -t'."
fi

log "Done."
log "Live at: https://$DOMAIN"
log "Container: docker logs -f $CONTAINER_NAME"
log "Rollback: see rollback.md (image tags: $(docker images $CONTAINER_NAME --format '{{.Tag}}' | grep -v '^<' | tr '\n' ' '))"
