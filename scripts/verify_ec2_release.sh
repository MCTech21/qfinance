#!/usr/bin/env bash
set -euo pipefail

WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"

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
  echo "[INFO] Buscando patrones prohibidos en frontend/build..."
  if grep -RInE 'emergentagent|expense-tracker|preview\.emergentagent\.com' frontend/build/; then
    echo "[ERROR] Se encontraron patrones prohibidos en frontend/build/." >&2
    exit 1
  fi
  echo "[OK] frontend/build limpio de emergentagent/expense-tracker."
}

check_served_main_js() {
  echo "[INFO] Validando JS servido por nginx en ${WEB_URL}/login ..."
  local main_js
  main_js=$(curl -fsSL "${WEB_URL}/login" | grep -oE '/static/js/main\.[^"]+\.js' | head -n 1)
  if [[ -z "${main_js}" ]]; then
    echo "[ERROR] No se pudo extraer /static/js/main.*.js del HTML servido." >&2
    exit 1
  fi

  if curl -fsSL "${WEB_URL}${main_js}" | grep -Eiq 'emergentagent|expense-tracker|preview\.emergentagent\.com'; then
    echo "[ERROR] El JS servido contiene patrones prohibidos." >&2
    exit 1
  fi

  echo "[OK] JS servido limpio: ${main_js}"
}

check_seed_demo() {
  echo "[INFO] Probando POST ${WEB_URL}/api/seed-demo-data ..."
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${WEB_URL}/api/seed-demo-data")
  if [[ "${code}" != "200" ]]; then
    echo "[ERROR] /api/seed-demo-data respondió HTTP ${code} (esperado 200)." >&2
    exit 1
  fi
  echo "[OK] /api/seed-demo-data respondió 200."
}

check_no_versioned_env
check_build_strings
check_served_main_js
check_seed_demo

echo "[OK] Checklist final EC2 completado."
