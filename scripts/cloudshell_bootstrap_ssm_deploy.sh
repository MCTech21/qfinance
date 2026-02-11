#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   REPO_URL=<https-or-ssh-url> bash scripts/cloudshell_bootstrap_ssm_deploy.sh
# Behavior:
#   - Reuse ~/qfinance_git or ~/qfinance when present.
#   - Clone into ~/qfinance_git only if missing.
#   - Update main/master and run SSM deploy runner.

if ! command -v git >/dev/null 2>&1; then
  echo "[ERROR] git is required." >&2
  exit 2
fi

HOME_DIR="${HOME:-/home/cloudshell-user}"
TARGET_DIR=""

if [[ -d "${HOME_DIR}/qfinance_git/.git" ]]; then
  TARGET_DIR="${HOME_DIR}/qfinance_git"
elif [[ -d "${HOME_DIR}/qfinance/.git" ]]; then
  TARGET_DIR="${HOME_DIR}/qfinance"
else
  if [[ -z "${REPO_URL:-}" ]]; then
    echo "[ERROR] No existing repo found in ~/qfinance_git or ~/qfinance." >&2
    echo "[HINT] Set REPO_URL and rerun, e.g.:" >&2
    echo "       REPO_URL=<repo-url> bash scripts/cloudshell_bootstrap_ssm_deploy.sh" >&2
    exit 3
  fi
  TARGET_DIR="${HOME_DIR}/qfinance_git"
  git clone "${REPO_URL}" "${TARGET_DIR}"
fi

cd "${TARGET_DIR}"
echo "USING_LOCAL_REPO=${TARGET_DIR}"

git fetch --all --prune
if git ls-remote --heads origin main | grep -q 'refs/heads/main'; then
  git checkout main
else
  git checkout master
fi

git pull --ff-only

if [[ -f "./run_ssm_deploy_qfinance.sh" ]]; then
  exec bash ./run_ssm_deploy_qfinance.sh
elif [[ -f "./scripts/run_ssm_deploy_qfinance.sh" ]]; then
  exec bash ./scripts/run_ssm_deploy_qfinance.sh
else
  echo "[ERROR] Missing SSM runner script in ${TARGET_DIR}." >&2
  exit 4
fi
