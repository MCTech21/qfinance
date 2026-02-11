#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
DEPLOY_TARGET_DIR="${DEPLOY_TARGET_DIR:-/var/www/qfinance}"
ENABLE_SWAP="${ENABLE_SWAP:-1}"
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT:-0}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"

if [[ "${ENABLE_SWAP}" == "1" ]]; then
  "${ROOT_DIR}/scripts/ec2_enable_swap.sh"
fi

"${ROOT_DIR}/scripts/build_frontend.sh"

echo "[INFO] Publicando build en ${DEPLOY_TARGET_DIR}..."
sudo mkdir -p "${DEPLOY_TARGET_DIR}"
sudo rsync -a --delete "${FRONTEND_DIR}/build/" "${DEPLOY_TARGET_DIR}/"

echo "[INFO] Verificando configuración nginx..."
sudo nginx -t
sudo systemctl reload nginx

echo "[INFO] Validando JS servido en ${WEB_URL}/login ..."
MAIN_JS_PATH=$(curl -fsSL "${WEB_URL}/login" | grep -oE '/static/js/main\.[^"]+\.js' | head -n 1)
if [[ -z "${MAIN_JS_PATH}" ]]; then
  echo "[ERROR] No se pudo detectar main.*.js en HTML servido." >&2
  exit 1
fi

if curl -fsSL "${WEB_URL}${MAIN_JS_PATH}" | grep -Eiq 'emergentagent|expense-tracker|preview\.emergentagent\.com'; then
  echo "[ERROR] El JS servido contiene patrones prohibidos." >&2
  exit 1
fi

echo "[OK] JS servido sin patrones prohibidos: ${MAIN_JS_PATH}"

if [[ "${VERIFY_SEED_ENDPOINT}" == "1" ]]; then
  echo "[INFO] Probando endpoint POST ${WEB_URL}/api/seed-demo-data ..."
  curl -fsS -X POST "${WEB_URL}/api/seed-demo-data" >/dev/null
  echo "[OK] Endpoint /api/seed-demo-data respondió correctamente."
fi

echo "[OK] Deploy frontend finalizado."
