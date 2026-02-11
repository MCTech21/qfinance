#!/usr/bin/env bash
set -euo pipefail

# Uso:
#   WEB_URL=http://52.53.215.40:8088 bash scripts/cloudshell_sync_and_deploy.sh
# Opcionales:
#   BRANCH=main ENABLE_SWAP=0 VERIFY_SEED_ENDPOINT=1
#   Nota: en CloudShell ENABLE_SWAP=0 evita errores de swapon (default de este script).

BRANCH="${BRANCH:-main}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
ENABLE_SWAP="${ENABLE_SWAP:-0}"
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT:-1}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[ERROR] Ejecuta este script dentro del repo git." >&2
  exit 1
fi

echo "[INFO] Sincronizando repo local con origin/${BRANCH} ..."
git fetch --all --prune
git checkout "${BRANCH}"
git reset --hard "origin/${BRANCH}"
git clean -fd

echo "[INFO] Estado después de sync:"
git status -sb

echo "[INFO] Iniciando deploy frontend (WEB_URL=${WEB_URL}) ..."
WEB_URL="${WEB_URL}" ENABLE_SWAP="${ENABLE_SWAP}" VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT}" scripts/deploy_frontend_ec2.sh

echo "[INFO] Verificación final explícita contra host servido ..."
WEB_URL="${WEB_URL}" VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT}" scripts/verify_ec2_release.sh

echo "[OK] CloudShell sync + deploy completado sin desfaces."
