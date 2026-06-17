#!/bin/bash
# deploy.sh — CustomerHub production deploy script
#
# Run from the repo root on the production server:
#   bash scripts/deploy.sh
#
# Prerequisites:
#   - .env.prod exists and is populated (copy from .env.prod.example)
#   - Python venv exists: cd backend && python -m venv venv
#   - Nginx installed and nginx/nginx.conf symlinked to /etc/nginx/nginx.conf
#   - /var/www/customerhub/ exists and is writable by this user
#   - Docker + docker compose v2 plugin installed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATIC_DIR="/var/www/customerhub"

cd "$REPO_ROOT"

echo ""
echo "=========================================="
echo "  CustomerHub deploy — $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# ── Step 1: Pull latest code ──────────────────────────────────────────────────
echo ""
echo "[1/6] Pulling latest code..."
git pull

# ── Step 2: Build frontend ────────────────────────────────────────────────────
echo ""
echo "[2/6] Building frontend..."
cd frontend
npm ci --prefer-offline
npm run build
echo "      Copying dist/ -> $STATIC_DIR"
sudo mkdir -p "$STATIC_DIR"
sudo rsync -a --delete dist/ "$STATIC_DIR/"
cd "$REPO_ROOT"

# ── Step 3: Install Python dependencies ───────────────────────────────────────
echo ""
echo "[3/6] Installing backend dependencies..."
cd backend
source venv/bin/activate
pip install -r requirements.txt --quiet
cd "$REPO_ROOT"

# ── Step 4: Run database migrations ───────────────────────────────────────────
echo ""
echo "[4/6] Running Alembic migrations..."
# Load DB_URL from .env.prod so alembic can connect to the production database
set -o allexport
source .env.prod
set +o allexport
cd backend
source venv/bin/activate
alembic upgrade head
cd "$REPO_ROOT"

# ── Step 5: Rebuild and restart backend containers ────────────────────────────
echo ""
echo "[5/6] Restarting backend services..."
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d --no-deps backend celery_worker celery_beat

# ── Step 6: Reload Nginx (picks up any conf changes) ─────────────────────────
echo ""
echo "[6/6] Reloading Nginx..."
sudo nginx -t && sudo nginx -s reload

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Deploy done."
echo "  Version: $(git rev-parse --short HEAD)"
echo "  URL:     https://customerhub.osd.vn"
echo "=========================================="
