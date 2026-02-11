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
