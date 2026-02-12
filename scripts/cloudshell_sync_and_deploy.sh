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
MIN_FREE_MB="${MIN_FREE_MB:-350}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[ERROR] Ejecuta este script dentro del repo git." >&2
  exit 1
fi

show_space() {
  echo "[INFO] Espacio en disco (repo):"
  df -h . | sed 's/^/[INFO] /'
  echo "[INFO] Inodos disponibles (repo):"
  df -i . | sed 's/^/[INFO] /'
}

free_mb() {
  df -Pm . | awk 'NR==2 {print $4}'
}

cleanup_low_space() {
  echo "[WARN] Ejecutando limpieza para recuperar espacio..."
  rm -rf frontend/node_modules frontend/build /tmp/qfinance-npm-cache || true
  npm cache clean --force >/dev/null 2>&1 || true
  rm -f .git/index.lock .git/packed-refs.lock .git/shallow.lock || true
  find .git/refs -name '*.lock' -type f -delete 2>/dev/null || true
  git reflog expire --expire=now --all >/dev/null 2>&1 || true
  git gc --prune=now >/dev/null 2>&1 || true
  show_space
}

ensure_space() {
  local current
  current="$(free_mb)"
  show_space
  if [[ "${current}" -lt "${MIN_FREE_MB}" ]]; then
    echo "[WARN] Espacio libre bajo (${current}MB < ${MIN_FREE_MB}MB)."
    cleanup_low_space
  fi
}

sync_repo() {
  echo "[INFO] Sincronizando repo local con origin/${BRANCH} ..."
  set +e
  local out
  out=$(git fetch --all --prune 2>&1)
  local code=$?
  set -e
  echo "${out}"

  if [[ ${code} -ne 0 ]]; then
    if echo "${out}" | grep -Eiq 'No space left on device|cannot lock ref|index\.lock'; then
      echo "[WARN] Falló git fetch por espacio/bloqueos. Intentando recuperación automática..."
      cleanup_low_space
      git fetch --all --prune
    else
      return ${code}
    fi
  fi

  git checkout "${BRANCH}"
  rm -f .git/index.lock .git/packed-refs.lock .git/shallow.lock || true
  find .git/refs -name '*.lock' -type f -delete 2>/dev/null || true
  git reset --hard "origin/${BRANCH}"
  git clean -fd
}

ensure_space
sync_repo

echo "[INFO] Estado después de sync:"
git status -sb

echo "[INFO] Iniciando deploy frontend (WEB_URL=${WEB_URL}) ..."
WEB_URL="${WEB_URL}" ENABLE_SWAP="${ENABLE_SWAP}" VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT}" scripts/deploy_frontend_ec2.sh

echo "[INFO] Verificación final explícita contra host servido ..."
WEB_URL="${WEB_URL}" VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT}" scripts/verify_ec2_release.sh

echo "[OK] CloudShell sync + deploy completado sin desfaces."
