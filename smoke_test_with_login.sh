#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/scripts/smoke_test_with_login.sh"

if [[ ! -f "$TARGET" ]]; then
  echo "[ERROR] No se encontró $TARGET" >&2
  echo "[INFO] Asegúrate de estar en la raíz del repo actualizado y ejecuta:" >&2
  echo "       git fetch --all --prune && git pull --ff-only" >&2
  exit 1
fi

exec bash "$TARGET" "$@"
