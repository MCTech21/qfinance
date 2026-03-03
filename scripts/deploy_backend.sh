#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

echo "[deploy-backend] restart service qfinance-backend"
sudo systemctl restart qfinance-backend
sudo systemctl is-active --quiet qfinance-backend

echo "[deploy-backend] api healthcheck"
curl -fsS "http://127.0.0.1:8088/api/health" >/dev/null

echo "[deploy-backend] ok"
