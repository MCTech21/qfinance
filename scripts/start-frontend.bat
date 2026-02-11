@echo off
setlocal
cd /d %~dp0\..\frontend

if not exist node_modules (
  echo [INFO] Instalando dependencias de frontend con yarn...
  yarn install
)

if not exist .env.local (
  echo [INFO] Generando frontend\.env.local por defecto...
  (
    echo REACT_APP_BACKEND_URL=http://localhost:8000
    echo WDS_SOCKET_PORT=3000
  ) > .env.local
)

echo [INFO] Iniciando React en http://localhost:3000
yarn start
