# Admin Console + Reset DEMO

## Alcance
Se agregó consola de administración en `/admin` (solo rol `admin`) con CRUD para:
- empresas
- proyectos
- catalogo_partidas
- proveedores
- usuarios

## Reglas implementadas
- Soft-delete por default: `is_active=false`.
- Listados admin filtran activos por default, con `include_inactive=true` para ver inactivos.
- Restauración por endpoint `POST /api/admin/catalogs/{entidad}/{id}/restore`.
- Guardrail de hard delete con referencias (`409`).
- Movimientos `posted` no editables ni eliminables; se habilita `POST /api/admin/movimientos/{id}/reverse`.
- `POST /api/admin/reset-demo` exige confirmación exacta `RESET DEMO`.
- `GET /api/admin/reset-demo/preview` muestra conteos demo.
- Audit log admin para create/update/delete/restore/reverse/reset con before/after, resultado e ip/user-agent.

## Bootstrap admin
Script: `scripts/bootstrap_admin.sh` (recomendado para CloudShell)

Defaults operativos configurados:
- email: `encargado.finanzas@quantumgrupo.mx`
- username/name: `MoisesFinanzas`

Comando recomendado (exacto para tu caso):
```bash
bash scripts/bootstrap_admin.sh --mode api --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --deactivate-demo-users
```

También puedes usar variables:
```bash
ADMIN_EMAIL=encargado.finanzas@quantumgrupo.mx ADMIN_USERNAME=MoisesFinanzas bash scripts/bootstrap_admin.sh --mode api --deactivate-demo-users
```

## Endpoints principales
- `GET /api/admin/catalogs/{entity}`
- `POST /api/admin/catalogs/{entity}`
- `PUT /api/admin/catalogs/{entity}/{id}`
- `DELETE /api/admin/catalogs/{entity}/{id}` (`hard_delete=true` opcional)
- `POST /api/admin/catalogs/{entity}/{id}/restore`
- `GET /api/admin/movimientos`
- `PUT /api/admin/movimientos/{id}`
- `DELETE /api/admin/movimientos/{id}`
- `POST /api/admin/movimientos/{id}/reverse`
- `GET /api/admin/reset-demo/preview`
- `POST /api/admin/reset-demo`


> Si estás en CloudShell sin libs Python de backend, el script usa **API mode** por defecto.
> Variables opcionales para autenticar admin existente:
> `QFINANCE_API_BASE_URL`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`.


> Recomendación CloudShell: usa `--mode api` para evitar timeouts a `localhost:27017` cuando Mongo no es accesible desde la shell.
