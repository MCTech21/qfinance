#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/frontend"
WEBROOT="/var/www/qfinance"
NGINX_SITE="/etc/nginx/sites-enabled/qfinance-8088"

echo "[deploy-frontend] build frontend"
cd "${FRONTEND_DIR}"
yarn build

echo "[deploy-frontend] sync to ${WEBROOT}"
sudo mkdir -p "${WEBROOT}"
sudo rsync -a --delete "${FRONTEND_DIR}/build/" "${WEBROOT}/"

if [[ -f "${NGINX_SITE}" ]]; then
  echo "[deploy-frontend] validating nginx"
  sudo nginx -t
  sudo systemctl reload nginx
else
  echo "[deploy-frontend] nginx site not found at ${NGINX_SITE}, skipping reload"
fi

echo "[deploy-frontend] healthcheck html"
curl -fsS "http://127.0.0.1:8088/" >/dev/null
echo "[deploy-frontend] ok"
