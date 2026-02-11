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

## Usuarios Demo

| Email | Contraseña | Rol |
|-------|------------|-----|
| admin@finrealty.com | admin123 | Administrador |
| finanzas@finrealty.com | finanzas123 | Finanzas |
| autorizador@finrealty.com | auth123 | Autorizador |
| lectura@finrealty.com | lectura123 | Solo Lectura |

## Semáforo de Cumplimiento

- 🟢 **Verde**: Ejercido ≤ 90% del presupuesto
- 🟡 **Amarillo**: Ejercido entre 90% y 100%
- 🔴 **Rojo**: Ejercido > 100% (requiere autorización)

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

Si ya hiciste merge y quieres desplegar en EC2 vía SSM, usa:

```bash
# 1) En CloudShell, entra a un checkout existente o clona uno nuevo
cd ~
if [ -d qfinance_git/.git ]; then
  cd qfinance_git
elif [ -d qfinance/.git ]; then
  cd qfinance
else
  # Usa la URL del botón "Code" de GitHub (HTTPS o SSH)
  git clone <REPO_URL> qfinance_git
  cd qfinance_git
fi

git fetch --all --prune
git checkout main || git checkout master
git pull --ff-only

# 2) Ejecuta runner SSM
bash run_ssm_deploy_qfinance.sh
```

Salida esperada al final:
- `COMMAND_ID=...`
- `FINAL_STATUS=Success`
- `DEPLOYING_COMMIT=...`
- `VERIFY_EXIT_CODE=0`

> Si ves `bash: scripts/run_ssm_deploy_qfinance.sh: No such file or directory`,
> estás fuera del checkout del repo. Entra al directorio del repo (`cd ~/qfinance_git`)
> y vuelve a ejecutar el comando.

Diagnóstico rápido en CloudShell cuando todo marca "No such file or directory":

```bash
pwd
ls -la
# si NO ves README.md y carpeta scripts/, aún no estás dentro del repo
```


Checklist rápido “no env versionados” (excluye `.env.example`):

```bash
git ls-files frontend/.env frontend/.env.local frontend/.env.production
# esperado: vacío
```
