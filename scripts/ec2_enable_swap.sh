#!/usr/bin/env bash
set -euo pipefail

SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"
SWAPFILE="${SWAPFILE:-/swapfile}"
SWAP_REQUIRED="${SWAP_REQUIRED:-0}"

if [[ "${SWAP_SIZE_GB}" -le 0 ]]; then
  echo "[INFO] SWAP_SIZE_GB <= 0, no se realizará configuración de swap."
  exit 0
fi

run_privileged() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

if run_privileged swapon --show | grep -q "${SWAPFILE}"; then
  echo "[INFO] Swap ya activo en ${SWAPFILE}."
  exit 0
fi

create_swapfile() {
  run_privileged fallocate -l "${SWAP_SIZE_GB}G" "${SWAPFILE}" || \
    run_privileged dd if=/dev/zero of="${SWAPFILE}" bs=1M count="$((SWAP_SIZE_GB * 1024))"
  run_privileged chmod 600 "${SWAPFILE}"
  run_privileged mkswap "${SWAPFILE}"
  run_privileged swapon "${SWAPFILE}"
  if ! run_privileged grep -q "^${SWAPFILE} " /etc/fstab; then
    echo "${SWAPFILE} none swap sw 0 0" | run_privileged tee -a /etc/fstab >/dev/null
  fi
}

echo "[INFO] Creando swap ${SWAP_SIZE_GB}G en ${SWAPFILE}..."
if create_swapfile; then
  echo "[OK] Swap activo:"
  run_privileged swapon --show || true
  exit 0
fi

# Reintento seguro si quedó un swapfile inválido a medias.
echo "[WARN] Primer intento de swap falló; limpiando e intentando de nuevo..."
run_privileged swapoff "${SWAPFILE}" >/dev/null 2>&1 || true
run_privileged rm -f "${SWAPFILE}" || true
if create_swapfile; then
  echo "[OK] Swap activo después de reintento:"
  run_privileged swapon --show || true
  exit 0
fi

if [[ "${SWAP_REQUIRED}" == "1" ]]; then
  echo "[ERROR] No se pudo habilitar swap y SWAP_REQUIRED=1." >&2
  exit 1
fi

echo "[WARN] No se pudo habilitar swap en este entorno (continuando porque SWAP_REQUIRED=0)." >&2
exit 0
