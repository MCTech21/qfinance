#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-frontend/build}"
PATTERN='emergentagent|expense-tracker|preview\.emergentagent\.com'

if [[ ! -d "${TARGET_DIR}" ]]; then
  echo "[ERROR] No existe directorio para validar: ${TARGET_DIR}" >&2
  exit 1
fi

if grep -RInE "${PATTERN}" "${TARGET_DIR}"; then
  echo "[ERROR] Se detectaron patrones prohibidos en ${TARGET_DIR}." >&2
  exit 1
fi

echo "[OK] Validación anti-hardcode completada: sin emergentagent/expense-tracker."
