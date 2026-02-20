#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

SKIP_INSTALL="${SKIP_INSTALL:-0}"
ALLOW_INSTALL_FAILURE="${ALLOW_INSTALL_FAILURE:-0}"

log_info() {
  echo "[INFO] $*"
}

log_warn() {
  echo "[WARN] $*"
}

log_error() {
  echo "[ERROR] $*"
}

install_deps() {
  log_info "Upgrading pip/wheel"
  python -m pip install --disable-pip-version-check --upgrade pip wheel || return 1

  log_info "Installing backend dependencies from backend/requirements.txt"
  python -m pip install --disable-pip-version-check -r requirements.txt || return 1

  if [[ -f requirements-dev.txt ]]; then
    log_info "Installing backend/requirements-dev.txt"
    python -m pip install --disable-pip-version-check -r requirements-dev.txt || return 1
  elif [[ -f requirements-test.txt ]]; then
    log_info "Installing backend/requirements-test.txt"
    python -m pip install --disable-pip-version-check -r requirements-test.txt || return 1
  else
    log_info "No requirements-dev.txt or requirements-test.txt found"
  fi
}

log_info "Preparing backend virtualenv at $VENV_DIR"
cd "$BACKEND_DIR"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ "$SKIP_INSTALL" == "1" ]]; then
  log_info "SKIP_INSTALL=1: skipping dependency installation"
else
  log_info "Installing backend dependencies..."
  if ! install_deps; then
    log_warn "Dependency install failed (likely no network/proxy)."
    if [[ "$ALLOW_INSTALL_FAILURE" == "1" ]]; then
      log_warn "ALLOW_INSTALL_FAILURE=1: continuing to pytest with existing env."
    else
      log_error "Install failed and ALLOW_INSTALL_FAILURE!=1. Exiting."
      exit 1
    fi
  fi
fi

cd "$ROOT_DIR"
log_info "Running pytest -q ${*:-}"
pytest -q "$@"
