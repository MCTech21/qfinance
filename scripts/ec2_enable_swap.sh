#!/usr/bin/env bash
set -euo pipefail

SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"
SWAPFILE="${SWAPFILE:-/swapfile}"

if [[ "${SWAP_SIZE_GB}" -le 0 ]]; then
  echo "[INFO] SWAP_SIZE_GB <= 0, no se realizará configuración de swap."
  exit 0
fi

if sudo swapon --show | grep -q "${SWAPFILE}"; then
  echo "[INFO] Swap ya activo en ${SWAPFILE}."
  exit 0
fi

echo "[INFO] Creando swap ${SWAP_SIZE_GB}G en ${SWAPFILE}..."
sudo fallocate -l "${SWAP_SIZE_GB}G" "${SWAPFILE}" || sudo dd if=/dev/zero of="${SWAPFILE}" bs=1M count="$((SWAP_SIZE_GB * 1024))"
sudo chmod 600 "${SWAPFILE}"
sudo mkswap "${SWAPFILE}"
sudo swapon "${SWAPFILE}"
if ! grep -q "^${SWAPFILE} " /etc/fstab; then
  echo "${SWAPFILE} none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi

echo "[OK] Swap activo:"
sudo swapon --show
