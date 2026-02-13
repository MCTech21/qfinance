# QFinance - Control Presupuestal Multiempresa

Sistema de control financiero y presupuestal para desarrollos inmobiliarios.

## Características

- **Dashboard** con KPIs en tiempo real
- **Control de Presupuestos** por empresa y proyecto
- **Gestión de Movimientos** financieros
- **Reportes** con detalle por partida y semáforo de cumplimiento
- **Catálogos** de empresas, proyectos y partidas contables
- **Multiempresa**: Altitud 3, Terraviva Desarrollos, Grupo Q
- **Multi-moneda**: MXN y USD con tipo de cambio

## Stack Tecnológico

- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Base de datos**: MongoDB

## Requisitos locales (Windows)

1. **Python 3.11+** (con launcher `py` disponible)
2. **Node.js 18+**
3. **Yarn Classic 1.x**
4. **MongoDB** en local en `mongodb://localhost:27017`

## Variables de entorno

### Backend (`backend/.env`)

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=qfinance
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
JWT_SECRET=change-me-in-local
```

### Frontend (`frontend/.env.local`)

```env
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_ENABLE_POSTHOG=false
WDS_SOCKET_PORT=3000
```

> Si no existen estos archivos, los scripts de arranque los crean automáticamente con esos valores por defecto.
> En producción, si `REACT_APP_BACKEND_URL` está vacío o no existe, el frontend usa rutas relativas (`/api/...`).
> Usa `frontend/.env.example` como referencia (se versiona porque es plantilla sin secretos) y evita versionar `.env` reales por ambiente.

## Arranque local (Windows)

### Opción recomendada: scripts (una terminal para cada servicio)

#### 1) Backend (FastAPI)

```bat
scripts\start-backend.bat
```

- Crea `backend/.venv` si no existe.
- Instala dependencias de `backend/requirements.txt`.
- Crea `backend/.env` con valores locales por defecto (si falta).
- Levanta API en: `http://localhost:8000`

#### 2) Frontend (React)

```bat
scripts\start-frontend.bat
```

- Instala dependencias de `frontend/package.json` (si falta `node_modules`).
- Crea `frontend/.env.local` con URL local al backend (si falta).
- Levanta app en: `http://localhost:3000`

## Health check de arranque

Con backend y frontend arriba:

1. Backend raíz:
   - Abrir `http://localhost:8000/`
   - Esperado: JSON con `{"status":"ok"...}`
2. Swagger:
   - Abrir `http://localhost:8000/docs`
3. Frontend:
   - Abrir `http://localhost:3000`
4. CORS:
   - El frontend debe poder iniciar sesión y consultar `/api/auth/me` sin error de CORS.
5. Health API:
   - Abrir `http://localhost:8000/api/health`
   - Esperado: `{"status":"ok","api":"up"}`
6. Analytics (opcional):
   - Con `REACT_APP_ENABLE_POSTHOG=false` no carga PostHog y no hay reintentos en bucle si hay AdBlock.

## Arranque manual (alternativo)

### Backend

```bat
cd backend
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bat
cd frontend
yarn install
yarn start
```

## Usuarios

No se incluyen credenciales preconfiguradas por defecto.

- Para promover tu cuenta real a administrador usa: `python scripts/bootstrap_admin.py --mode api --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas`.

## Semáforo de Cumplimiento

- 🟢 **Verde**: Ejercido ≤ 90% del presupuesto
- 🟡 **Amarillo**: Ejercido entre 90% y 100%
- 🔴 **Rojo**: Ejercido > 100% (requiere autorización)


## EC2-first deploy (CloudShell ligero)

Desde ahora, CloudShell **no debe clonar/buildar local**. Solo orquesta deploy en EC2.

```bash
EC2_HOST=52.53.215.40 \
WEB_URL=http://52.53.215.40:8088 \
ENABLE_SWAP=0 MIN_FREE_MB=600 \
bash scripts/cloudshell_sync_and_deploy.sh
```

Variables requeridas/recomendadas:
- `EC2_HOST` (ssh), `EC2_USER` (default `ubuntu`)
- `WEB_URL`, `ENABLE_SWAP`, `MIN_FREE_MB`
- opcional: `EC2_WORK_DIR=/opt/qfinance_git`, `BRANCH=main`
- opcional SSM: `DEPLOY_TRANSPORT=ssm` + `EC2_INSTANCE_ID`

El trabajo pesado vive en EC2 en `scripts/ec2_sync_and_deploy.sh`.

## CloudShell (sync + deploy recomendado)

Después de cada merge/PR, ejecuta:

```bash
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```

Este comando ahora orquesta el deploy remoto EC2-first (sin git/build pesado en CloudShell).

Si CloudShell no tiene `yarn`, `scripts/build_frontend.sh` cae automáticamente a `npm install --legacy-peer-deps --no-package-lock` para evitar choques de peer deps sin ensuciar lockfiles.

## Deploy frontend en EC2 (nginx)

Arquitectura esperada en producción:
- nginx en `:8088` sirve archivos estáticos desde `/var/www/qfinance`.
- FastAPI en `127.0.0.1:8000`.
- nginx proxea `/api/*` hacia `127.0.0.1:8000` (same-origin, sin CORS entre frontend/backend).

Comandos recomendados:

```bash
# 1) Build robusto (OOM guard + validación anti-hardcode)
scripts/build_frontend.sh

# 2) Deploy robusto (build + rsync + nginx reload + validación final de main.*.js servido)
scripts/deploy_frontend_ec2.sh
```

Validaciones rápidas:

```bash
# Debe regresar vacío
grep -RInE 'emergentagent|expense-tracker|preview\.emergentagent\.com' frontend/build/

# Verifica que se sirva login y el JS principal desde nginx
curl -fsSL http://127.0.0.1:8088/login | head
```

Más detalle en `docs/ec2_deploy.md`.

### Deploy por AWS SSM desde CloudShell (sin SSH)

Para reducir conflictos de merge en este README, el runbook completo vive en:

- `docs/cloudshell_ssm_deploy.md`

Resumen rápido:

```bash
# Dentro del repo
bash run_ssm_deploy_qfinance.sh

# Si estás fuera del repo en CloudShell
REPO_URL=<REPO_URL> bash scripts/cloudshell_bootstrap_ssm_deploy.sh
```

Salida esperada al final:
- `COMMAND_ID=...`
- `FINAL_STATUS=Success`
- `DEPLOYING_COMMIT=...`
- `VERIFY_EXIT_CODE=0`

Checklist rápido “no env versionados” (excluye `.env.example`):

```bash
git ls-files frontend/.env frontend/.env.local frontend/.env.production
# esperado: vacío
```


### Troubleshooting (`No such file or directory`)

Si CloudShell marca `scripts/cloudshell_sync_and_deploy.sh: No such file or directory`, actualiza `main` y valida que exista en remoto:

```bash
git fetch --all --prune
git checkout main
git pull --ff-only origin main
git ls-tree -r --name-only origin/main | grep '^scripts/cloudshell_sync_and_deploy.sh$'
```

Fallback (sin script):

```bash
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 scripts/deploy_frontend_ec2.sh
WEB_URL=http://52.53.215.40:8088 scripts/verify_ec2_release.sh
```


### Troubleshooting (`ENOSPC` en CloudShell)

Si aparece `ENOSPC: no space left on device` durante `npm install`:

```bash
rm -rf frontend/node_modules frontend/build
npm cache clean --force || true
rm -rf /tmp/qfinance-npm-cache

df -h
WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```


### Troubleshooting (`Cannot find module 'ajv/dist/compile/codegen'`)

Si aparece ese error en CloudShell (path npm), ejecuta limpieza y reintento:

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
- si sigue fallando por `unpack-objects failed`/`failed to write object`, hace **reclone limpio automático** del repo (mismo remote/branch).

Puedes forzar un umbral mínimo de espacio libre (MB) antes del sync:

```bash
MIN_FREE_MB=600 WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 bash scripts/cloudshell_sync_and_deploy.sh
```


## Reset rápido de contraseña admin

```bash
QFINANCE_API_BASE_URL=http://52.53.215.40:8088/api BOOTSTRAP_ADMIN_EMAIL=admin@finrealty.com BOOTSTRAP_ADMIN_PASSWORD=admin123 python scripts/reset_admin_password.py --mode api --apply   --email encargado.finanzas@quantumgrupo.mx   --username MoisesFinanzas   --new-password 'NuevaClaveSegura!2026'
```

## Comando post-merge para actualizar frontend (CloudShell -> EC2)

```bash
EC2_HOST=52.53.215.40 WEB_URL=http://52.53.215.40:8088 ENABLE_SWAP=0 MIN_FREE_MB=600 bash scripts/cloudshell_sync_and_deploy.sh
```


## Seguridad de cuenta (first login)

- Existe flujo de cambio de contraseña desde **Mi Cuenta / Configuración**.
- Si un usuario tiene `must_change_password=true` (por ejemplo tras reset a contraseña temporal), el sistema obliga el flujo `/force-change-password` antes de permitir acceso al resto de módulos.

