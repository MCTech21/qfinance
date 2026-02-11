#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] scripts/deploy-frontend-ec2.sh está deprecado. Usando scripts/deploy_frontend_ec2.sh..."
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy_frontend_ec2.sh" "$@"
