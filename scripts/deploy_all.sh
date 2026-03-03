#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${ROOT_DIR}/deploy_frontend_8088.sh"
"${ROOT_DIR}/deploy_backend.sh"
echo "[deploy-all] done"
