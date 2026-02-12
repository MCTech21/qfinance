#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
NODE_MEMORY_MB="${NODE_MEMORY_MB:-4096}"
NODE_MEMORY_MB_SAFE="${NODE_MEMORY_MB_SAFE:-1536}"
FRONTEND_PM="${FRONTEND_PM:-auto}" # auto|yarn|npm
NPM_CACHE_DIR="${NPM_CACHE_DIR:-/tmp/qfinance-npm-cache}"

cd "${FRONTEND_DIR}"

export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=${NODE_MEMORY_MB}}"
echo "[INFO] NODE_OPTIONS=${NODE_OPTIONS}"

if ! command -v node >/dev/null 2>&1; then
  echo "[ERROR] node no está instalado en este entorno." >&2
  exit 1
fi

choose_pm() {
  case "${FRONTEND_PM}" in
    yarn|npm)
      echo "${FRONTEND_PM}"
      return 0
      ;;
    auto)
      if command -v yarn >/dev/null 2>&1; then
        echo "yarn"
      elif command -v npm >/dev/null 2>&1; then
        echo "npm"
      else
        echo ""
      fi
      return 0
      ;;
    *)
      echo ""
      return 0
      ;;
  esac
}

PM="$(choose_pm)"
if [[ -z "${PM}" ]]; then
  echo "[ERROR] No se encontró gestor de paquetes JS soportado (yarn/npm) o FRONTEND_PM inválido: ${FRONTEND_PM}." >&2
  exit 1
fi

echo "[INFO] Package manager seleccionado: ${PM}"

show_disk() {
  echo "[INFO] Espacio en disco (pwd=${PWD}):"
  df -h . | sed 's/^/[INFO] /'
}

npm_install_with_retry() {
  local log_file
  log_file="$(mktemp)"

  mkdir -p "${NPM_CACHE_DIR}"
  show_disk
  echo "[INFO] npm cache dir: ${NPM_CACHE_DIR}"

  set +e
  npm install --legacy-peer-deps --no-package-lock --cache "${NPM_CACHE_DIR}" 2>&1 | tee "${log_file}"
  local code=${PIPESTATUS[0]}
  set -e

  if [[ ${code} -eq 0 ]]; then
    rm -f "${log_file}"
    return 0
  fi

  if grep -Eiq 'ENOSPC|no space left on device' "${log_file}"; then
    echo "[WARN] npm install falló por ENOSPC. Limpiando artefactos y reintentando una vez..."
    rm -rf node_modules
    npm cache clean --force >/dev/null 2>&1 || true
    rm -rf "${NPM_CACHE_DIR}" || true
    mkdir -p "${NPM_CACHE_DIR}"
    show_disk

    set +e
    npm install --legacy-peer-deps --no-package-lock --cache "${NPM_CACHE_DIR}" 2>&1 | tee "${log_file}"
    code=${PIPESTATUS[0]}
    set -e
  fi

  rm -f "${log_file}"
  return ${code}
}


ensure_ajv_codegen() {
  if node -e "require.resolve('ajv/dist/compile/codegen')" >/dev/null 2>&1; then
    return 0
  fi

  echo "[WARN] Dependencia faltante: ajv/dist/compile/codegen. Aplicando reparación npm para webpack..."
  npm install --legacy-peer-deps --no-package-lock --cache "${NPM_CACHE_DIR}" ajv@^8.17.1 ajv-keywords@^5.1.0

  if ! node -e "require.resolve('ajv/dist/compile/codegen')" >/dev/null 2>&1; then
    echo "[ERROR] No se pudo resolver ajv/dist/compile/codegen después de la reparación." >&2
    return 1
  fi
}


run_build_with_retry() {
  local primary_cmd=("$@")
  local log_file
  log_file="$(mktemp)"

  set +e
  "${primary_cmd[@]}" 2>&1 | tee "${log_file}"
  local code=${PIPESTATUS[0]}
  set -e

  if [[ ${code} -eq 0 ]]; then
    rm -f "${log_file}"
    return 0
  fi

  if grep -Eiq 'exited too early|out of memory|heap out of memory|Killed' "${log_file}"; then
    echo "[WARN] Build falló por memoria. Reintentando en modo ahorro..."
    export GENERATE_SOURCEMAP=false
    export DISABLE_ESLINT_PLUGIN=true
    export NODE_OPTIONS="--max-old-space-size=${NODE_MEMORY_MB_SAFE}"
    echo "[INFO] NODE_OPTIONS(retry)=${NODE_OPTIONS}"
    echo "[INFO] GENERATE_SOURCEMAP=${GENERATE_SOURCEMAP} DISABLE_ESLINT_PLUGIN=${DISABLE_ESLINT_PLUGIN}"

    set +e
    "${primary_cmd[@]}" 2>&1 | tee "${log_file}"
    code=${PIPESTATUS[0]}
    set -e
  fi

  rm -f "${log_file}"
  return ${code}
}

echo "[INFO] Instalando dependencias frontend..."
if [[ "${PM}" == "yarn" ]]; then
  yarn install --frozen-lockfile
else
  npm_install_with_retry
  ensure_ajv_codegen
fi

echo "[INFO] Build frontend..."
if [[ "${PM}" == "yarn" ]]; then
  run_build_with_retry yarn build
else
  run_build_with_retry npm run build
fi

echo "[INFO] Verificando artefactos sin dominios prohibidos..."
"${ROOT_DIR}/scripts/check_no_emergentagent.sh" "${FRONTEND_DIR}/build"

echo "[OK] Build frontend listo para deploy."
