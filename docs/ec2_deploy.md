# Deploy de frontend en EC2 (nginx + FastAPI)

## Topología esperada
- Frontend estático servido por nginx en `:8088` con root `/var/www/qfinance`.
- Backend FastAPI escuchando en `127.0.0.1:8000`.
- nginx proxea `/api/*` hacia `127.0.0.1:8000`.

## P0 - Build seguro
```bash
scripts/build_frontend.sh
```

Qué hace:
- Instala dependencias del frontend con `yarn install --frozen-lockfile`.
- Fuerza `NODE_OPTIONS=--max-old-space-size=4096` (configurable).
- Ejecuta `yarn build`.
- Falla si detecta `emergentagent`, `expense-tracker` o `preview.emergentagent.com` en `frontend/build`.

## P1 - Deploy seguro
```bash
scripts/deploy_frontend_ec2.sh
```

Qué hace:
- (Opcional) habilita swap si no existe (`scripts/ec2_enable_swap.sh`).
- Ejecuta build seguro (`scripts/build_frontend.sh`).
- Publica con `rsync --delete frontend/build/ /var/www/qfinance/` solo si el build fue exitoso.
- Ejecuta `nginx -t` y `systemctl reload nginx`.
- Descarga el `main.*.js` servido y valida que no tenga patrones prohibidos.

## Validaciones rápidas
```bash
# Debe quedar vacío
grep -RInE 'emergentagent|expense-tracker|preview\.emergentagent\.com' frontend/build/

# Debe responder HTML y referenciar static/js/main.*.js
curl -fsSL http://127.0.0.1:8088/login | head

# Opcional: validar endpoint demo
curl -fsS -X POST http://127.0.0.1:8088/api/seed-demo-data
```

## Checklist final de verificación (EC2)

También puedes ejecutar todo en bloque:

```bash
scripts/verify_ec2_release.sh
```

Checks individuales:

```bash
# 1) No env reales versionados (NO incluye .env.example)
git ls-files frontend/.env frontend/.env.local frontend/.env.production
# Esperado: salida vacía

# 2) Build sin hardcodes prohibidos
grep -RInE 'emergentagent|expense-tracker|preview\.emergentagent\.com' frontend/build/
# Esperado: salida vacía

# 3) JS servido por nginx sin hardcodes
MAIN_JS=$(curl -fsSL http://127.0.0.1:8088/login | grep -oE '/static/js/main\.[^" ]+\.js' | head -n 1)
curl -fsSL "http://127.0.0.1:8088${MAIN_JS}" | grep -Eiq 'emergentagent|expense-tracker|preview\.emergentagent\.com' && echo "FAIL" || echo "OK"
# Esperado: OK

# 4) Endpoint demo responde 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8088/api/seed-demo-data
# Esperado: 200
```

### ¿Por qué `frontend/.env.example` sí se versiona?
- Es una **plantilla de configuración pública** sin secretos.
- Estandariza variables esperadas para dev/CI/ops.
- Evita documentar valores sensibles en `.env` reales.


## Admin Console + Reset DEMO

- Consola admin disponible en `/admin` (requiere rol admin).
- Reset DEMO desde UI: exige teclear `RESET DEMO`.
- Para bootstrap admin:

```bash
python scripts/bootstrap_admin.py --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --deactivate-demo-users
```

- El seed (`POST /api/seed-demo-data`) marca registros como `is_demo=true` para permitir reset selectivo.
