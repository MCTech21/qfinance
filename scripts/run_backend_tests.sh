#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

cd "$BACKEND_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Best-effort upgrade; continue if restricted network blocks package index.
python -m pip install --disable-pip-version-check --upgrade pip wheel || \
  echo "[WARN] Could not upgrade pip/wheel; continuing with existing tooling"

python -m pip install --disable-pip-version-check -r requirements.txt

if [[ -f requirements-dev.txt ]]; then
  python -m pip install --disable-pip-version-check -r requirements-dev.txt
fi
if [[ -f requirements-test.txt ]]; then
  python -m pip install --disable-pip-version-check -r requirements-test.txt
fi

cd "$ROOT_DIR"
pytest -q "$@"
