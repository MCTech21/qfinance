# Deploy de frontend en EC2 (nginx + FastAPI)

## Topología esperada
- Frontend estático servido por nginx en `:8088` con root `/var/www/qfinance`.
- Backend FastAPI escuchando en `127.0.0.1:8000`.
- nginx proxea `/api/*` hacia `127.0.0.1:8000`.


## CloudShell: sync + deploy sin desface

Usa este comando único después de cada merge/PR para evitar código viejo local:

```bash
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```

Este flujo hace:
- `fetch + checkout + reset --hard + clean` contra `origin/main`.
- build + publish (`rsync --delete`) + reload de nginx.
- verificación post-deploy contra el host servido.

> Si tu entorno no permite activar swap (por ejemplo, `swapon ... Invalid argument`), el deploy ya no se detiene por eso cuando `SWAP_REQUIRED=0` (default).

## P0 - Build seguro
```bash
scripts/build_frontend.sh
```

Qué hace:
- Instala dependencias con `yarn` (preferido) o hace fallback a `npm install --legacy-peer-deps --no-package-lock` si `yarn` no existe.
- Fuerza `NODE_OPTIONS=--max-old-space-size=4096` (configurable).
- Ejecuta build con el gestor detectado y, si detecta error por memoria, reintenta en modo ahorro (`NODE_MEMORY_MB_SAFE`, `GENERATE_SOURCEMAP=false`, `DISABLE_ESLINT_PLUGIN=true`).
- Falla si detecta `emergentagent`, `expense-tracker` o `preview.emergentagent.com` en `frontend/build`.

## P1 - Deploy seguro
```bash
scripts/deploy_frontend_ec2.sh
```

Qué hace:
- (Opcional) habilita swap si no existe (`scripts/ec2_enable_swap.sh`).
- En CloudShell se recomienda `ENABLE_SWAP=0` para evitar `swapon ... Invalid argument`.
- Ejecuta build seguro (`scripts/build_frontend.sh`).
- Publica con `rsync --delete frontend/build/ /var/www/qfinance/` solo si el build fue exitoso.
- Ejecuta `nginx -t` y `systemctl reload nginx`.
- Descarga el `main.*.js` servido y valida que no tenga patrones prohibidos.

## Validaciones rápidas
```bash
# Debe quedar vacío
grep -RInEi 'emergentagent|emergent\.sh|app\.emergent\.sh|utm_source=emergent-badge|Made with Emergent|expense-tracker|preview\.emergentagent\.com|admin@finrealty\.com|finanzas@finrealty\.com|autorizador@finrealty\.com|lectura@finrealty\.com|Usuarios demo|Cargar datos demo' frontend/build/

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
grep -RInEi 'emergentagent|emergent\.sh|app\.emergent\.sh|utm_source=emergent-badge|Made with Emergent|expense-tracker|preview\.emergentagent\.com|admin@finrealty\.com|finanzas@finrealty\.com|autorizador@finrealty\.com|lectura@finrealty\.com|Usuarios demo|Cargar datos demo' frontend/build/
# Esperado: salida vacía

# 3) JS servido por nginx sin hardcodes
MAIN_JS=$(curl -fsSL http://127.0.0.1:8088/login | grep -oE '/static/js/main\.[^" ]+\.js' | head -n 1)
curl -fsSL "http://127.0.0.1:8088${MAIN_JS}" | grep -Eiq 'emergentagent|emergent\.sh|app\.emergent\.sh|utm_source=emergent-badge|Made with Emergent|expense-tracker|preview\.emergentagent\.com|admin@finrealty\.com|finanzas@finrealty\.com|autorizador@finrealty\.com|lectura@finrealty\.com|Usuarios demo|Cargar datos demo' && echo "FAIL" || echo "OK"
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
bash scripts/bootstrap_admin.sh --mode api --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --deactivate-demo-users
```

- El seed (`POST /api/seed-demo-data`) marca registros como `is_demo=true` para permitir reset selectivo.


- Si CloudShell no tiene dependencias Python del backend, el bootstrap usa API mode.
  Puedes parametrizar:

```bash
QFINANCE_API_BASE_URL=http://127.0.0.1:8088/api BOOTSTRAP_ADMIN_EMAIL=admin@finrealty.com BOOTSTRAP_ADMIN_PASSWORD=admin123 \
  bash scripts/bootstrap_admin.sh --mode api --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --deactivate-demo-users
```


### Limpieza de usuarios demo heredados

```bash
python scripts/cleanup_demo_users.py --dry-run
python scripts/cleanup_demo_users.py --apply
```

> El script elimina usuarios `@finrealty.com` y garantiza que `encargado.finanzas@quantumgrupo.mx` quede activo/admin.


### Troubleshooting: `scripts/cloudshell_sync_and_deploy.sh: No such file or directory`

Si CloudShell responde ese error, tu checkout local aún no trae el script nuevo. Ejecuta:

```bash
git fetch --all --prune
git checkout main
git pull --ff-only origin main
git ls-tree -r --name-only origin/main | grep '^scripts/cloudshell_sync_and_deploy.sh$'
```

Si el último comando no imprime nada, tu `origin/main` todavía no contiene ese cambio.

**Fallback inmediato (sin ese script):**

```bash
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 scripts/deploy_frontend_ec2.sh
WEB_URL=http://52.53.215.40:8088 scripts/verify_ec2_release.sh
```


### Troubleshooting: `ENOSPC: no space left on device` durante npm install

El build script ya reintenta automáticamente una vez cuando detecta ENOSPC (limpia `node_modules` + cache npm temporal en `/tmp/qfinance-npm-cache`).

Si aún falla en CloudShell, libera espacio y reintenta:

```bash
rm -rf frontend/node_modules frontend/build
npm cache clean --force || true
rm -rf /tmp/qfinance-npm-cache

df -h
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```


### Troubleshooting: `Cannot find module 'ajv/dist/compile/codegen'`

En fallback con npm, el build script ya intenta autorreparar esta dependencia (`ajv` + `ajv-keywords`) antes de compilar.

Si persiste en CloudShell, limpia módulos/cache y reintenta:

```bash
rm -rf frontend/node_modules frontend/build
npm cache clean --force || true
rm -rf /tmp/qfinance-npm-cache

WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```


### Troubleshooting: `The build failed because the process exited too early`

Ese error suele ser falta de memoria en CloudShell. El script ya reintenta automáticamente en modo ahorro.

También puedes forzarlo manualmente:

```bash
NODE_MEMORY_MB=2048 NODE_MEMORY_MB_SAFE=1024 WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```


### Troubleshooting: `cannot lock ref ... No space left on device`

Si `git fetch` falla en CloudShell por falta de espacio/bloqueos (`index.lock`, `refs/.../HEAD.lock`), el script `scripts/cloudshell_sync_and_deploy.sh` ya intenta recuperación automática:
- limpia `frontend/node_modules`, `frontend/build`, `/tmp/qfinance-npm-cache`
- limpia locks de `.git`
- ejecuta `git gc --prune=now`
- reintenta `git fetch --all --prune`

Puedes forzar un umbral mínimo de espacio libre (MB) antes del sync:

```bash
MIN_FREE_MB=600 WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```
