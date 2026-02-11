@echo off
setlocal
cd /d %~dp0\..\backend

if not exist .venv (
  echo [INFO] Creando entorno virtual en backend\.venv ...
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt

if not exist .env (
  echo [INFO] Generando backend\.env por defecto...
  (
    echo MONGO_URL=mongodb://localhost:27017
    echo DB_NAME=qfinance
    echo CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    echo JWT_SECRET=change-me-in-local
  ) > .env
)

echo [INFO] Iniciando FastAPI en http://localhost:8000
uvicorn server:app --reload --host 0.0.0.0 --port 8000
