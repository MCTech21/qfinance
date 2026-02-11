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
