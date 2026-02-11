#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
DEPLOY_TARGET_DIR="${DEPLOY_TARGET_DIR:-/var/www/qfinance}"
ENABLE_SWAP="${ENABLE_SWAP:-1}"
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT:-1}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
SKIP_NGINX_RELOAD="${SKIP_NGINX_RELOAD:-0}"

run_privileged() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

if [[ "${ENABLE_SWAP}" == "1" ]]; then
  "${ROOT_DIR}/scripts/ec2_enable_swap.sh"
fi

echo "[INFO] Limpiando build previo en ${FRONTEND_DIR}/build ..."
rm -rf "${FRONTEND_DIR}/build"

"${ROOT_DIR}/scripts/build_frontend.sh"

echo "[INFO] Publicando build en ${DEPLOY_TARGET_DIR}..."
run_privileged mkdir -p "${DEPLOY_TARGET_DIR}"
run_privileged rsync -a --delete "${FRONTEND_DIR}/build/" "${DEPLOY_TARGET_DIR}/"

if [[ "${SKIP_NGINX_RELOAD}" == "1" ]]; then
  echo "[INFO] SKIP_NGINX_RELOAD=1, omitiendo nginx -t/reload (modo no-EC2)."
else
  echo "[INFO] Verificando configuración nginx..."
  run_privileged nginx -t
  if command -v systemctl >/dev/null 2>&1; then
    run_privileged systemctl reload nginx
  else
    run_privileged service nginx reload
  fi
fi

echo "[INFO] Ejecutando verificación final post-deploy..."
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT}" WEB_URL="${WEB_URL}" "${ROOT_DIR}/scripts/verify_ec2_release.sh"

echo "[OK] Deploy frontend finalizado."
