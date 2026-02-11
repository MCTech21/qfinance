#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="${ROOT_DIR}/scripts/run_ssm_deploy_qfinance.sh"

if [[ ! -f "${SCRIPT_PATH}" ]]; then
  echo "[ERROR] Could not find ${SCRIPT_PATH}." >&2
  echo "[HINT] Run this from a valid qfinance checkout, for example:" >&2
  echo "       cd ~/qfinance_git && bash run_ssm_deploy_qfinance.sh" >&2
  exit 1
fi

exec bash "${SCRIPT_PATH}" "$@"
