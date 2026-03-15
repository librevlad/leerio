#!/usr/bin/env bash
# Deploy Leerio to VPS — works without GitHub Actions.
#
# Usage:
#   From local machine:  ./scripts/deploy.sh
#   On VPS directly:     ./scripts/deploy.sh --local
#
# Requires:
#   Local: VPS_HOST, VPS_USER, VPS_KEY env vars (or ~/.ssh/leerio-vps key)
#   VPS:   /opt/leerio repo + .env with all secrets
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}>>>${NC} $*"; }
warn() { echo -e "${YELLOW}>>>${NC} $*"; }
err()  { echo -e "${RED}>>>${NC} $*" >&2; }

# ── Local deploy (runs on VPS) ───────────────────────────────────────────

deploy_local() {
  cd /opt/leerio

  # Save rollback point
  PREV_SHA=$(git rev-parse HEAD)
  log "Current: $PREV_SHA"

  # Fix ownership on git-tracked files that Docker may have chowned
  chown -f "$(id -u):$(id -g)" data/.gitignore data/.gitkeep 2>/dev/null || true

  # Pull latest
  git fetch origin main
  git reset --hard origin/main
  NEW_SHA=$(git rev-parse HEAD)
  log "Updated: $NEW_SHA"

  if [[ "$PREV_SHA" == "$NEW_SHA" ]]; then
    warn "Already up to date. Rebuilding anyway..."
  fi

  # Ensure production config
  rm -f docker-compose.override.yml
  if grep -q 'CORS_ORIGINS=https://leerio.app' .env 2>/dev/null; then
    sed -i 's|CORS_ORIGINS=https://leerio.app|CORS_ORIGINS=https://app.leerio.app|' .env
  fi

  # Verify required env vars exist
  for var in GOOGLE_CLIENT_ID JWT_SECRET S3_ENDPOINT S3_ACCESS_KEY S3_SECRET_KEY S3_BUCKET; do
    if ! grep -q "^${var}=" .env 2>/dev/null; then
      err "Missing $var in .env — deploy aborted"
      exit 1
    fi
  done

  # Build and deploy
  log "Building containers..."
  docker compose build --pull --no-cache app
  docker compose build --pull server

  log "Starting services..."
  docker compose up -d --wait --wait-timeout 120

  # Restore git-tracked file permissions (entrypoint chowns /data for appuser)
  git checkout -- data/.gitignore data/.gitkeep 2>/dev/null || true

  # Health check
  log "Verifying services..."

  for i in 1 2 3 4 5; do
    if curl -sf https://app.leerio.app/api/config/constants > /dev/null 2>&1; then
      log "Health check passed (attempt $i)"
      log "Deploy complete!"
      docker compose ps
      exit 0
    fi
    warn "Health check failed (attempt $i/5), retrying in 10s..."
    sleep 10
  done

  # Rollback
  err "All health checks failed — rolling back to $PREV_SHA"
  git checkout "$PREV_SHA"
  docker compose build --pull server
  docker compose build --pull --no-cache app
  docker compose up -d
  err "Rolled back. Check logs: docker compose logs"
  exit 1
}

# ── Main ─────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--local" ]]; then
  deploy_local
  exit 0
fi

# ── Remote mode: SSH into VPS and run --local ────────────────────────────

VPS_HOST="${VPS_HOST:-}"
VPS_USER="${VPS_USER:-root}"
VPS_KEY="${VPS_KEY:-$HOME/.ssh/leerio-vps}"

if [[ -z "$VPS_HOST" ]]; then
  err "VPS_HOST not set. Export it or add to .env:"
  err "  export VPS_HOST=your-vps-ip"
  err "  export VPS_USER=root"
  err "  export VPS_KEY=~/.ssh/leerio-vps"
  exit 1
fi

if [[ ! -f "$VPS_KEY" ]]; then
  err "SSH key not found: $VPS_KEY"
  err "Set VPS_KEY to the correct path."
  exit 1
fi

log "Deploying to $VPS_USER@$VPS_HOST..."

# Push current branch to origin first so VPS can pull
BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "Pushing $BRANCH to origin..."
git push origin "$BRANCH"

# SSH and run deploy on VPS
ssh -i "$VPS_KEY" -o StrictHostKeyChecking=accept-new "$VPS_USER@$VPS_HOST" \
  "cd /opt/leerio && bash scripts/deploy.sh --local"
