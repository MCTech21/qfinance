#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${FRONTEND_DIR:-${ROOT_DIR}/frontend}"
NODE_MEMORY_MB="${NODE_MEMORY_MB:-4096}"
FRONTEND_PM="${FRONTEND_PM:-auto}" # auto|yarn|npm

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

echo "[INFO] Instalando dependencias frontend..."
if [[ "${PM}" == "yarn" ]]; then
  yarn install --frozen-lockfile
else
  npm install
fi

echo "[INFO] Build frontend..."
if [[ "${PM}" == "yarn" ]]; then
  yarn build
else
  npm run build
fi

echo "[INFO] Verificando artefactos sin dominios prohibidos..."
"${ROOT_DIR}/scripts/check_no_emergentagent.sh" "${FRONTEND_DIR}/build"

echo "[OK] Build frontend listo para deploy."
