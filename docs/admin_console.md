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
Script: `scripts/bootstrap_admin.py`

Defaults operativos configurados:
- email: `encargado.finanzas@quantumgrupo.mx`
- username/name: `MoisesFinanzas`

Comando recomendado (exacto para tu caso):
```bash
python scripts/bootstrap_admin.py --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --deactivate-demo-users
```

También puedes usar variables:
```bash
ADMIN_EMAIL=encargado.finanzas@quantumgrupo.mx ADMIN_USERNAME=MoisesFinanzas python scripts/bootstrap_admin.py --deactivate-demo-users
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
