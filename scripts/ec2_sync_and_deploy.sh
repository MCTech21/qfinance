#!/usr/bin/env bash
set -euo pipefail

# Ejecutar en EC2 (no en CloudShell)
# Idempotente: asegura repo, sincroniza main y corre deploy frontend + verify.

EC2_WORK_DIR="${EC2_WORK_DIR:-/opt/qfinance_git}"
REPO_URL="${REPO_URL:-git@github.com:MCTech21/qfinance.git}"
BRANCH="${BRANCH:-main}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
ENABLE_SWAP="${ENABLE_SWAP:-0}"
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT:-1}"
MIN_FREE_MB="${MIN_FREE_MB:-350}"

run_privileged() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

log_space() {
  local target="${1:-.}"
  echo "[INFO] Disk usage (${target}):"
  df -h "${target}" | sed 's/^/[INFO] /'
  echo "[INFO] Inode usage (${target}):"
  df -i "${target}" | sed 's/^/[INFO] /'
}

assert_space_health() {
  local target="${1:-.}"
  local free_mb inode_use
  free_mb=$(df -Pm "${target}" | awk 'NR==2 {print $4}')
  inode_use=$(df -Pi "${target}" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')

  if [[ -z "${free_mb}" || -z "${inode_use}" ]]; then
    echo "[ERROR] No se pudo evaluar espacio/inodos en ${target}." >&2
    exit 1
  fi

  if [[ "${free_mb}" -lt "${MIN_FREE_MB}" ]]; then
    echo "[ERROR] Espacio libre insuficiente en ${target}: ${free_mb}MB < MIN_FREE_MB=${MIN_FREE_MB}." >&2
    exit 1
  fi

  if [[ "${inode_use}" -gt 95 ]]; then
    echo "[ERROR] Uso de inodos crítico en ${target}: IUse%=${inode_use} (>95)." >&2
    exit 1
  fi
}

ensure_repo() {
  local parent_dir
  parent_dir="$(dirname "${EC2_WORK_DIR}")"

  run_privileged mkdir -p "${parent_dir}"

  if [[ ! -d "${EC2_WORK_DIR}/.git" ]]; then
    echo "[INFO] Repo no existe en ${EC2_WORK_DIR}; clonando ${REPO_URL} (${BRANCH}) ..."
    run_privileged rm -rf "${EC2_WORK_DIR}"
    run_privileged git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${EC2_WORK_DIR}"
    return
  fi

  echo "[INFO] Repo existente en ${EC2_WORK_DIR}; sincronizando con origin/${BRANCH} ..."
  run_privileged git -C "${EC2_WORK_DIR}" fetch --all --prune
  run_privileged git -C "${EC2_WORK_DIR}" checkout "${BRANCH}"
  run_privileged git -C "${EC2_WORK_DIR}" reset --hard "origin/${BRANCH}"
  run_privileged git -C "${EC2_WORK_DIR}" clean -fd
}

main() {
  echo "[INFO] Iniciando flujo EC2-first"
  echo "[INFO] EC2_WORK_DIR=${EC2_WORK_DIR} BRANCH=${BRANCH} WEB_URL=${WEB_URL} ENABLE_SWAP=${ENABLE_SWAP} MIN_FREE_MB=${MIN_FREE_MB}"

  log_space "$(dirname "${EC2_WORK_DIR}")"
  assert_space_health "$(dirname "${EC2_WORK_DIR}")"

  ensure_repo

  log_space "${EC2_WORK_DIR}"
  assert_space_health "${EC2_WORK_DIR}"

  echo "[INFO] Ejecutando deploy frontend en EC2 ..."
  run_privileged bash -lc "cd '${EC2_WORK_DIR}' && WEB_URL='${WEB_URL}' ENABLE_SWAP='${ENABLE_SWAP}' VERIFY_SEED_ENDPOINT='${VERIFY_SEED_ENDPOINT}' bash scripts/deploy_frontend_ec2.sh"

  echo "[INFO] Ejecutando verificación final en EC2 ..."
  run_privileged bash -lc "cd '${EC2_WORK_DIR}' && WEB_URL='${WEB_URL}' VERIFY_SEED_ENDPOINT='${VERIFY_SEED_ENDPOINT}' bash scripts/verify_ec2_release.sh"

  echo "[OK] EC2-first deploy completado."
}

main "$@"
