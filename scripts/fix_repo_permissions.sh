#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-$(pwd)}"
if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "[ERROR] '$REPO_DIR' no parece un repo git (falta .git)." >&2
  exit 1
fi

USER_NAME="${SUDO_USER:-${USER:-$(id -un)}}"
GROUP_NAME="$(id -gn "$USER_NAME")"

echo "[INFO] Repo: $REPO_DIR"
echo "[INFO] Corrigiendo ownership a ${USER_NAME}:${GROUP_NAME} ..."
if command -v sudo >/dev/null 2>&1; then
  sudo chown -R "${USER_NAME}:${GROUP_NAME}" "$REPO_DIR"
else
  chown -R "${USER_NAME}:${GROUP_NAME}" "$REPO_DIR"
fi

echo "[INFO] Corrigiendo permisos de escritura..."
find "$REPO_DIR/.git" -type d -exec chmod u+rwx {} +
find "$REPO_DIR/.git" -type f -exec chmod u+rw {} +

# Limpieza de locks huérfanos
rm -f "$REPO_DIR/.git/index.lock" "$REPO_DIR/.git/packed-refs.lock"

if [[ -d "$REPO_DIR/.git/objects" ]]; then
  find "$REPO_DIR/.git/objects" -type f -name '*.lock' -delete || true
fi

echo "[OK] Permisos corregidos. Ahora ejecuta:"
echo "     cd '$REPO_DIR'"
echo "     git fetch --all --prune && git pull --ff-only"
