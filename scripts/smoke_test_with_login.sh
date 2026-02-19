#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Uso:
  $(basename "$0") --base-url URL --email EMAIL --password PASSWORD [opciones]

Opciones:
  --company-id ID        company_id para probar summary filtrado (opcional)
  --project-id ID        project_id para probar summary filtrado (opcional)
  --movement-id ID       movement_id para descargar recibo PDF (opcional)
  --out-dir DIR          directorio de salida para artefactos (default: /tmp/qfinance-smoke)

Ejemplo:
  $(basename "$0") \
    --base-url https://api.tudominio.com \
    --email admin@qfinance.local \
    --password 'SuperSecret123' \
    --company-id 123 --project-id 456
USAGE
}

BASE_URL=""
EMAIL=""
PASSWORD=""
COMPANY_ID=""
PROJECT_ID=""
MOVEMENT_ID=""
OUT_DIR="/tmp/qfinance-smoke"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url) BASE_URL="${2:-}"; shift 2 ;;
    --email) EMAIL="${2:-}"; shift 2 ;;
    --password) PASSWORD="${2:-}"; shift 2 ;;
    --company-id) COMPANY_ID="${2:-}"; shift 2 ;;
    --project-id) PROJECT_ID="${2:-}"; shift 2 ;;
    --movement-id) MOVEMENT_ID="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Opción desconocida: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$BASE_URL" || -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "[ERROR] --base-url, --email y --password son obligatorios." >&2
  usage
  exit 1
fi

mkdir -p "$OUT_DIR"
BASE_URL="${BASE_URL%/}"
LOGIN_FILE="$OUT_DIR/login.json"
CLIENTS_FILE="$OUT_DIR/clients.json"
SUMMARY_FILE="$OUT_DIR/inventory_summary.json"
SUMMARY_FILTERED_FILE="$OUT_DIR/inventory_summary_filtered.json"
ME_FILE="$OUT_DIR/me.json"
RECEIPT_FILE="$OUT_DIR/receipt.pdf"

json_escape() {
  python3 - <<'PY' "$1"
import json,sys
print(json.dumps(sys.argv[1]))
PY
}

EMAIL_JSON=$(json_escape "$EMAIL")
PASSWORD_JSON=$(json_escape "$PASSWORD")

echo "[1/6] Login con usuario/contraseña..."
LOGIN_PAYLOAD="{\"email\":${EMAIL_JSON},\"password\":${PASSWORD_JSON}}"
HTTP_CODE=$(curl -sS -o "$LOGIN_FILE" -w "%{http_code}" \
  -H 'Content-Type: application/json' \
  -d "$LOGIN_PAYLOAD" \
  "$BASE_URL/api/auth/login")

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[ERROR] Login falló con HTTP $HTTP_CODE" >&2
  cat "$LOGIN_FILE" >&2
  exit 1
fi

TOKEN=$(python3 - <<'PY' "$LOGIN_FILE"
import json,sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data=json.load(f)
print(data.get('access_token',''))
PY
)

if [[ -z "$TOKEN" ]]; then
  echo "[ERROR] La respuesta de login no incluyó access_token." >&2
  cat "$LOGIN_FILE" >&2
  exit 1
fi

echo "[OK] Login correcto. Token obtenido automáticamente."

auth_get() {
  local url="$1"
  local out="$2"
  local code
  code=$(curl -sS -o "$out" -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$url")
  echo "$code"
}

echo "[2/6] Validando /api/auth/me ..."
ME_CODE=$(auth_get "$BASE_URL/api/auth/me" "$ME_FILE")
if [[ "$ME_CODE" != "200" ]]; then
  echo "[ERROR] /api/auth/me falló con HTTP $ME_CODE" >&2
  cat "$ME_FILE" >&2
  exit 1
fi

echo "[3/6] Consultando /api/clients (enriquecido)..."
CLIENTS_CODE=$(auth_get "$BASE_URL/api/clients" "$CLIENTS_FILE")
if [[ "$CLIENTS_CODE" != "200" ]]; then
  echo "[ERROR] /api/clients falló con HTTP $CLIENTS_CODE" >&2
  cat "$CLIENTS_FILE" >&2
  exit 1
fi

echo "[4/6] Consultando /api/inventory/summary global..."
SUMMARY_CODE=$(auth_get "$BASE_URL/api/inventory/summary" "$SUMMARY_FILE")
if [[ "$SUMMARY_CODE" != "200" ]]; then
  echo "[ERROR] /api/inventory/summary falló con HTTP $SUMMARY_CODE" >&2
  cat "$SUMMARY_FILE" >&2
  exit 1
fi

if [[ -n "$COMPANY_ID" || -n "$PROJECT_ID" ]]; then
  QS=()
  [[ -n "$COMPANY_ID" ]] && QS+=("company_id=$COMPANY_ID")
  [[ -n "$PROJECT_ID" ]] && QS+=("project_id=$PROJECT_ID")
  QUERY="$(IFS='&'; echo "${QS[*]}")"
  echo "[5/6] Consultando /api/inventory/summary filtrado (${QUERY})..."
  SUMMARY_FILTERED_CODE=$(auth_get "$BASE_URL/api/inventory/summary?$QUERY" "$SUMMARY_FILTERED_FILE")
  if [[ "$SUMMARY_FILTERED_CODE" != "200" ]]; then
    echo "[ERROR] /api/inventory/summary filtrado falló con HTTP $SUMMARY_FILTERED_CODE" >&2
    cat "$SUMMARY_FILTERED_FILE" >&2
    exit 1
  fi
else
  echo "[5/6] Saltando summary filtrado (sin --company-id/--project-id)."
fi

if [[ -n "$MOVEMENT_ID" ]]; then
  echo "[6/6] Descargando recibo PDF /api/movements/$MOVEMENT_ID/receipt.pdf ..."
  RECEIPT_CODE=$(curl -sS -o "$RECEIPT_FILE" -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/api/movements/$MOVEMENT_ID/receipt.pdf")
  if [[ "$RECEIPT_CODE" != "200" ]]; then
    echo "[ERROR] Receipt PDF falló con HTTP $RECEIPT_CODE" >&2
    exit 1
  fi
  echo "[OK] Recibo guardado en: $RECEIPT_FILE"
else
  echo "[6/6] Saltando descarga de recibo (sin --movement-id)."
fi

echo
echo "=== RESUMEN ==="
python3 - <<'PY' "$ME_FILE" "$CLIENTS_FILE" "$SUMMARY_FILE"
import json,sys
me=json.load(open(sys.argv[1],encoding='utf-8'))
clients=json.load(open(sys.argv[2],encoding='utf-8'))
summary=json.load(open(sys.argv[3],encoding='utf-8'))
print(f"Usuario: {me.get('email')} | rol={me.get('role')} | empresa={me.get('empresa_id')}")
print(f"Clientes: {len(clients) if isinstance(clients,list) else 'n/a'}")
if isinstance(clients,list) and clients:
    first=clients[0]
    keys=['id','nombre','inventory_clave','valor_total_mxn','abonos_total_mxn','saldo_restante_mxn']
    snap={k:first.get(k) for k in keys}
    print(f"Primer cliente (campos clave): {snap}")
print(f"Summary inventario: {summary}")
PY

echo "Artefactos JSON en: $OUT_DIR"
