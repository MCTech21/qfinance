#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-frontend/build}"
PATTERN='emergentagent|emergent\.sh|app\.emergent\.sh|utm_source=emergent-badge|Made with Emergent|expense-tracker|preview\.emergentagent\.com|admin@finrealty\.com|finanzas@finrealty\.com|autorizador@finrealty\.com|lectura@finrealty\.com|Usuarios demo|Cargar datos demo'

if [[ ! -d "${TARGET_DIR}" ]]; then
  echo "[ERROR] No existe directorio para validar: ${TARGET_DIR}" >&2
  exit 1
fi

if grep -RInEi "${PATTERN}" "${TARGET_DIR}"; then
  echo "[ERROR] Se detectaron patrones prohibidos en ${TARGET_DIR}." >&2
  exit 1
fi

echo "[OK] Validación anti-hardcode completada: sin referencias demo/emergent prohibidas."
