#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
NODE_MEMORY_MB="${NODE_MEMORY_MB:-4096}"

cd "${FRONTEND_DIR}"

export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=${NODE_MEMORY_MB}}"
echo "[INFO] NODE_OPTIONS=${NODE_OPTIONS}"

echo "[INFO] Instalando dependencias frontend..."
yarn install --frozen-lockfile

echo "[INFO] Build frontend..."
yarn build

echo "[INFO] Verificando artefactos sin dominios prohibidos..."
"${ROOT_DIR}/scripts/check_no_emergentagent.sh" "${FRONTEND_DIR}/build"

echo "[OK] Build frontend listo para deploy."
