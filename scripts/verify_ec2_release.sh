#!/usr/bin/env bash
set -euo pipefail

WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
BUILD_DIR="${BUILD_DIR:-frontend/build}"

FORBIDDEN_PATTERN='emergentagent|emergent\.sh|app\.emergent\.sh|utm_source=emergent-badge|Made with Emergent|expense-tracker|preview\.emergentagent\.com|admin@finrealty\.com|finanzas@finrealty\.com|autorizador@finrealty\.com|lectura@finrealty\.com'

check_no_versioned_env() {
  echo "[INFO] Verificando env no versionados (excepto .env.example)..."
  if git ls-files frontend/.env frontend/.env.local frontend/.env.production | grep -q .; then
    echo "[ERROR] Hay archivos .env reales versionados en frontend." >&2
    git ls-files frontend/.env frontend/.env.local frontend/.env.production
    exit 1
  fi
  echo "[OK] No hay frontend/.env, frontend/.env.local ni frontend/.env.production versionados."
}

check_build_strings() {
  echo "[INFO] Buscando patrones prohibidos en ${BUILD_DIR}..."
  if [[ ! -d "${BUILD_DIR}" ]]; then
    echo "[ERROR] No existe ${BUILD_DIR}. Ejecuta scripts/build_frontend.sh primero." >&2
    exit 1
  fi

  if grep -RInEi "${FORBIDDEN_PATTERN}" "${BUILD_DIR}"; then
    echo "[ERROR] Se encontraron patrones prohibidos en ${BUILD_DIR}." >&2
    exit 1
  fi
  echo "[OK] ${BUILD_DIR} limpio de referencias prohibidas."
}

resolve_main_js_path() {
  local manifest_path="/asset-manifest.json"
  local manifest_json
  manifest_json=$(curl -fsSL "${WEB_URL}${manifest_path}" || true)

  if [[ -n "${manifest_json}" ]]; then
    local from_manifest
    from_manifest=$(printf '%s' "${manifest_json}" | sed -n 's|.*"main.js":"\([^"]*\)".*|\1|p' | head -n 1)
    if [[ -n "${from_manifest}" ]]; then
      printf '%s' "${from_manifest}"
      return 0
    fi
  fi

  curl -fsSL "${WEB_URL}/login" | grep -oE '/static/js/main\.[^"]+\.js' | head -n 1
}

check_served_main_js() {
  echo "[INFO] Validando JS servido por nginx en ${WEB_URL} ..."
  local main_js
  main_js="$(resolve_main_js_path)"

  if [[ -z "${main_js}" ]]; then
    echo "[ERROR] No se pudo extraer /static/js/main.*.js de asset-manifest ni HTML /login." >&2
    exit 1
  fi

  if curl -fsSL "${WEB_URL}${main_js}" | grep -Eiq "${FORBIDDEN_PATTERN}"; then
    echo "[ERROR] El JS servido contiene patrones prohibidos." >&2
    exit 1
  fi

  echo "[OK] JS servido limpio: ${main_js}"
}


check_no_versioned_env
check_build_strings
check_served_main_js

echo "[OK] Checklist final EC2 completado."
