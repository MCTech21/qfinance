#!/usr/bin/env bash
set -euo pipefail

# Ejecutar en EC2 (no en CloudShell)
# Idempotente: asegura repo, sincroniza main y corre deploy frontend + verify.

EC2_WORK_DIR="${EC2_WORK_DIR:-/opt/qfinance_git}"
REPO_URL="${REPO_URL:-git@github.com:MCTech21/qfinance.git}"
BRANCH="${BRANCH:-main}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
ENABLE_SWAP="${ENABLE_SWAP:-0}"
MIN_FREE_MB="${MIN_FREE_MB:-350}"
RESTART_BACKEND="${RESTART_BACKEND:-1}"
BACKEND_SERVICE_CANDIDATES="${BACKEND_SERVICE_CANDIDATES:-qfinance-backend qfinance-api qfinance finrealty-api}"
BACKEND_RESTART_COMMAND="${BACKEND_RESTART_COMMAND:-}"
BACKEND_VERIFY_PATH="${BACKEND_VERIFY_PATH:-/api/auth/change-password}"

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

restart_backend_if_available() {
  [[ "${RESTART_BACKEND}" == "1" ]] || {
    echo "[INFO] RESTART_BACKEND=0, omitiendo reinicio de backend."
    return
  }

  if [[ -n "${BACKEND_RESTART_COMMAND}" ]]; then
    echo "[INFO] Ejecutando BACKEND_RESTART_COMMAND personalizado..."
    run_privileged bash -lc "${BACKEND_RESTART_COMMAND}"
    echo "[OK] BACKEND_RESTART_COMMAND ejecutado."
    return
  fi

  if ! command -v systemctl >/dev/null 2>&1; then
    echo "[WARN] systemctl no disponible; omitiendo reinicio de backend."
    return
  fi

  local service
  for service in ${BACKEND_SERVICE_CANDIDATES}; do
    if run_privileged systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "${service}.service"; then
      echo "[INFO] Reiniciando backend service detectado: ${service}.service"
      run_privileged systemctl restart "${service}.service"
      run_privileged systemctl is-active --quiet "${service}.service"
      echo "[OK] Backend reiniciado: ${service}.service"
      return
    fi
  done

  echo "[WARN] No se detectó servicio backend conocido (${BACKEND_SERVICE_CANDIDATES})."
  echo "[WARN] Si usas otro nombre, exporta BACKEND_SERVICE_CANDIDATES='mi-service'"
  echo "[WARN] o BACKEND_RESTART_COMMAND='systemctl restart mi-service'."
}


log_backend_runtime_config() {
  local redacted_cmd="<empty>"
  if [[ -n "${BACKEND_RESTART_COMMAND}" ]]; then
    redacted_cmd="${BACKEND_RESTART_COMMAND}"
  fi

  echo "[INFO] Backend runtime config: RESTART_BACKEND=${RESTART_BACKEND} BACKEND_URL=${BACKEND_URL} BACKEND_VERIFY_PATH=${BACKEND_VERIFY_PATH}"
  echo "[INFO] Backend restart command: ${redacted_cmd}"
}

verify_backend_source_route() {
  local backend_file
  backend_file="${EC2_WORK_DIR}/backend/server.py"

  if [[ ! -f "${backend_file}" ]]; then
    echo "[WARN] No existe ${backend_file}; omitiendo verificación de código fuente backend."
    return
  fi

  if ! grep -q '"/auth/change-password"' "${backend_file}"; then
    echo "[ERROR] El código backend en ${backend_file} no contiene /auth/change-password." >&2
    echo "[ERROR] Commit desplegado: $(run_privileged git -C "${EC2_WORK_DIR}" rev-parse --short HEAD 2>/dev/null || echo desconocido)." >&2
    echo "[ERROR] Haz merge/cherry-pick del commit que agrega el endpoint y vuelve a desplegar." >&2
    exit 1
  fi

  echo "[OK] Código backend contiene /auth/change-password."
}

verify_backend_route() {
  local openapi
  openapi="$(curl -fsSL "${BACKEND_URL}/openapi.json" || true)"
  if [[ -z "${openapi}" ]]; then
    openapi="$(curl -fsSL "${BACKEND_URL}/api/openapi.json" || true)"
  fi

  if [[ -z "${openapi}" ]]; then
    echo "[ERROR] No se pudo obtener OpenAPI desde ${BACKEND_URL} (ni /openapi.json ni /api/openapi.json)." >&2
    exit 1
  fi

  if ! printf '%s' "${openapi}" | grep -q "\"${BACKEND_VERIFY_PATH}\""; then
    echo "[ERROR] Backend no expone ${BACKEND_VERIFY_PATH}." >&2
    echo "[ERROR] Esto causará 404 en el frontend para rutas nuevas." >&2
    echo "[ERROR] Revisa nombre del service y define BACKEND_RESTART_COMMAND si aplica." >&2
    exit 1
  fi

  echo "[OK] Backend expone ${BACKEND_VERIFY_PATH}."
}

main() {
  echo "[INFO] Iniciando flujo EC2-first"
  echo "[INFO] EC2_WORK_DIR=${EC2_WORK_DIR} BRANCH=${BRANCH} WEB_URL=${WEB_URL} BACKEND_URL=${BACKEND_URL} ENABLE_SWAP=${ENABLE_SWAP} MIN_FREE_MB=${MIN_FREE_MB}"

  log_space "$(dirname "${EC2_WORK_DIR}")"
  assert_space_health "$(dirname "${EC2_WORK_DIR}")"

  ensure_repo

  log_space "${EC2_WORK_DIR}"
  assert_space_health "${EC2_WORK_DIR}"

  log_backend_runtime_config
  verify_backend_source_route
  restart_backend_if_available

  echo "[INFO] Verificando rutas backend disponibles ..."
  verify_backend_route

  echo "[INFO] Ejecutando deploy frontend en EC2 ..."
  run_privileged bash -lc "cd '${EC2_WORK_DIR}' && WEB_URL='${WEB_URL}' ENABLE_SWAP='${ENABLE_SWAP}' bash scripts/deploy_frontend_ec2.sh"

  echo "[INFO] Ejecutando verificación final en EC2 ..."
  run_privileged bash -lc "cd '${EC2_WORK_DIR}' && WEB_URL='${WEB_URL}' bash scripts/verify_ec2_release.sh"

  echo "[OK] EC2-first deploy completado."
}

main "$@"
