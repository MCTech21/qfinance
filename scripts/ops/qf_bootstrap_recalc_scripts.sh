#!/usr/bin/env bash
set -euo pipefail

cat > ~/qf_recalc_client_balances_now.sh <<'INNER'
#!/usr/bin/env bash
set -euo pipefail
: "${CID:?Necesito CID=...}"

BACK=""
for d in "$HOME/QFinance/app/backend" "/opt/qfinance_git/app/backend"; do
  if [ -f "$d/server.py" ]; then BACK="$d"; break; fi
done
[ -n "$BACK" ] || { echo "ERROR: no encontré backend (server.py)."; exit 1; }

PYBIN="$BACK/.venv/bin/python3"
[ -x "$PYBIN" ] || PYBIN="python3"

cd "$BACK"
if [ -f /etc/qfinance/backend.env ]; then set -a; . /etc/qfinance/backend.env; set +a; fi
export DB_NAME="${DB_NAME:-qfinance}"

CID="$CID" "$PYBIN" - <<'PY'
import asyncio, os, server

CID = os.environ["CID"]

def _to_float(x):
    try:
        if x is None: return None
        if isinstance(x, (int,float)): return float(x)
        s = str(x).replace(",","").strip()
        return float(s)
    except Exception:
        return None

def _is_posted(m):
    s = m.get("status")
    if isinstance(s,str) and s.strip().lower()=="posted":
        return True
    return m.get("posted") is True

def _is_402_403(m):
    for k in ("partida_codigo","partida","partidaCodigo"):
        v = m.get(k)
        if v is None:
            continue
        try:
            if int(str(v).strip()) in (402,403):
                return True
        except Exception:
            pass
    return False

async def main():
    db = server.db
    mov = db["movements"]
    cli = db["clients"]

    q = {
      "$and":[
        {"$or":[{"client_id": CID},{"clientId": CID}]},
        {"$or":[{"status":{"$in":["posted","POSTED"]}}, {"posted": True}]},
        {"$or":[
          {"partida_codigo":{"$in":[402,403,"402","403"]}},
          {"partida":{"$in":[402,403,"402","403"]}},
          {"partidaCodigo":{"$in":[402,403,"402","403"]}}
        ]}
      ]
    }

    total = 0.0
    async for m in mov.find(q, {"amount_mxn":1,"amountMxn":1,"amount":1,"status":1,"posted":1,"partida_codigo":1,"partidaCodigo":1}):
        if not (_is_posted(m) and _is_402_403(m)):
            continue
        v = m.get("amount_mxn") or m.get("amountMxn") or m.get("amount") or 0
        total += (_to_float(v) or 0.0)

    c = await cli.find_one({"$or":[{"id": CID},{"_id": CID}]}) or {}

    # tratar de inferir el total base del cliente
    num_keys = [
      "precio_venta","precioVenta","precio_mxn","precioMxn","price","price_mxn","valor","valor_mxn",
      "monto_total","montoTotal","total","total_mxn","totalMxn","saldo_total","saldoTotal","saldo_inicial","saldoInicial",
      "valor_total","valorTotal"
    ]
    total_base = None
    for k in num_keys:
        vv = _to_float(c.get(k))
        if vv is not None and vv > 0:
            total_base = vv
            break

    if total_base is None:
        sr = _to_float(c.get("saldo_restante") or c.get("saldoRestante")) or 0.0
        ab = _to_float(c.get("abonos_acumulados") or c.get("abonosAcumulados")) or 0.0
        if sr > 0 or ab > 0:
            total_base = sr + ab

    upd = {
      "abonos_acumulados": round(total,2),
      "abonosAcumulados": round(total,2),
    }
    if total_base is not None:
        saldo = round(max(0.0, float(total_base) - float(total)), 2)
        upd["saldo_restante"] = saldo
        upd["saldoRestante"] = saldo

    await cli.update_one({"$or":[{"id": CID},{"_id": CID}]}, {"$set": upd})

    c2 = await cli.find_one({"$or":[{"id": CID},{"_id": CID}]}, {"id":1,"nombre":1,"name":1,"abonos_acumulados":1,"saldo_restante":1})
    print("CID:", CID)
    print("Cliente:", c2.get("nombre") or c2.get("name"))
    print("abonos_acumulados:", c2.get("abonos_acumulados"))
    print("saldo_restante:", c2.get("saldo_restante"))

asyncio.run(main())
PY
INNER
chmod +x ~/qf_recalc_client_balances_now.sh

cat > ~/qf_recalc_from_mid_now.sh <<'INNER'
#!/usr/bin/env bash
set -euo pipefail
: "${MID:?Necesito MID=...}"

BACK=""
for d in "$HOME/QFinance/app/backend" "/opt/qfinance_git/app/backend"; do
  if [ -f "$d/server.py" ]; then BACK="$d"; break; fi
done
[ -n "$BACK" ] || { echo "ERROR: no encontré backend (server.py)."; exit 1; }

PYBIN="$BACK/.venv/bin/python3"
[ -x "$PYBIN" ] || PYBIN="python3"

cd "$BACK"
if [ -f /etc/qfinance/backend.env ]; then set -a; . /etc/qfinance/backend.env; set +a; fi
export DB_NAME="${DB_NAME:-qfinance}"

MID="$MID" "$PYBIN" - <<'PY'
import asyncio, os, server

MID = os.environ["MID"]

def _to_float(x):
    try:
        if x is None: return None
        if isinstance(x, (int,float)): return float(x)
        s = str(x).replace(",","").strip()
        return float(s)
    except Exception:
        return None

def _is_posted(m):
    s = m.get("status")
    if isinstance(s,str) and s.strip().lower()=="posted":
        return True
    return m.get("posted") is True

def _is_402_403(m):
    for k in ("partida_codigo","partida","partidaCodigo"):
        v = m.get(k)
        if v is None:
            continue
        try:
            if int(str(v).strip()) in (402,403):
                return True
        except Exception:
            pass
    return False

async def main():
    db = server.db
    mov = db["movements"]
    cli = db["clients"]

    m = await mov.find_one({"$or":[{"id": MID},{"_id": MID}]}, {"id":1,"client_id":1,"clientId":1,"reference":1,"status":1,"posted":1,"partida_codigo":1,"partidaCodigo":1})
    if not m:
        print("No encontré movimiento:", MID)
        return

    cid = m.get("client_id") or m.get("clientId")
    print("MID:", m.get("id") or m.get("_id"))
    print("reference:", m.get("reference"))
    print("partida:", m.get("partida_codigo") or m.get("partidaCodigo"))
    print("status:", m.get("status"), "posted:", m.get("posted"))
    print("CID:", cid or "NO_TIENE_CLIENT_ID")
    if not cid:
        return

    # suma abonos
    q = {
      "$and":[
        {"$or":[{"client_id": cid},{"clientId": cid}]},
        {"$or":[{"status":{"$in":["posted","POSTED"]}}, {"posted": True}]},
        {"$or":[
          {"partida_codigo":{"$in":[402,403,"402","403"]}},
          {"partida":{"$in":[402,403,"402","403"]}},
          {"partidaCodigo":{"$in":[402,403,"402","403"]}}
        ]}
      ]
    }
    total = 0.0
    async for mm in mov.find(q, {"amount_mxn":1,"amountMxn":1,"amount":1,"status":1,"posted":1,"partida_codigo":1,"partidaCodigo":1}):
        if not (_is_posted(mm) and _is_402_403(mm)):
            continue
        v = mm.get("amount_mxn") or mm.get("amountMxn") or mm.get("amount") or 0
        total += (_to_float(v) or 0.0)

    c = await cli.find_one({"$or":[{"id": cid},{"_id": cid}]}, {"saldo_restante":1,"abonos_acumulados":1,"nombre":1,"name":1})
    sr = _to_float((c or {}).get("saldo_restante")) or 0.0
    ab = _to_float((c or {}).get("abonos_acumulados")) or 0.0
    total_base = sr + ab if (sr>0 or ab>0) else None

    upd = {"abonos_acumulados": round(total,2), "abonosAcumulados": round(total,2)}
    if total_base is not None:
        upd["saldo_restante"] = round(max(0.0, total_base - total), 2)
        upd["saldoRestante"] = upd["saldo_restante"]

    await cli.update_one({"$or":[{"id": cid},{"_id": cid}]}, {"$set": upd})
    c2 = await cli.find_one({"$or":[{"id": cid},{"_id": cid}]}, {"id":1,"nombre":1,"name":1,"abonos_acumulados":1,"saldo_restante":1})
    print("Cliente:", c2.get("nombre") or c2.get("name"))
    print("abonos_acumulados:", c2.get("abonos_acumulados"))
    print("saldo_restante:", c2.get("saldo_restante"))

asyncio.run(main())
PY
INNER
chmod +x ~/qf_recalc_from_mid_now.sh

echo "OK: scripts creados:"
ls -la ~/qf_recalc_client_balances_now.sh ~/qf_recalc_from_mid_now.sh
