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

## Troubleshooting (CloudShell)

Si recibes:

```bash
bootstrap_admin.py: error: unrecognized arguments: --mode api
```

tu copia local está desfasada y aún tiene una versión antigua de `scripts/bootstrap_admin.py`.

Verifica que tu script sí incluya `--mode`:

```bash
python scripts/bootstrap_admin.py --help | grep -- "--mode"
```

Si el comando no imprime `--mode`, sincroniza `main` y reintenta:

```bash
git fetch --all --prune
git checkout main
git pull --ff-only origin main
python scripts/bootstrap_admin.py --help | grep -- "--mode"
```


## Limpieza de usuarios DEMO (`@finrealty.com`)

Script idempotente: `scripts/cleanup_demo_users.py`

- **Dry-run (default):**

```bash
python scripts/cleanup_demo_users.py
```

- **Aplicar cambios:**

```bash
python scripts/cleanup_demo_users.py --apply
```

- Asegura que `encargado.finanzas@quantumgrupo.mx` quede activo + admin.
- Elimina usuarios `@finrealty.com`; si un delete falla, hace fallback a desactivación (`is_active=false`).

## Control de seed de usuarios demo

`POST /api/seed-demo-data` **ya no crea usuarios demo por default**.

Solo se crean si se define explícitamente:

```bash
SEED_DEMO_USERS=true
```

Por defecto, el seed solo limpia usuarios `is_demo=true` y preserva usuarios reales existentes.


## Reset de contraseña admin

Script: `scripts/reset_admin_password.py`

Dry-run:

```bash
python scripts/reset_admin_password.py --mode api --email encargado.finanzas@quantumgrupo.mx --username MoisesFinanzas --new-password 'NuevaClaveSegura!2026'
```

Aplicar:

```bash
QFINANCE_API_BASE_URL=http://52.53.215.40:8088/api BOOTSTRAP_ADMIN_EMAIL=admin@finrealty.com BOOTSTRAP_ADMIN_PASSWORD=admin123 python scripts/reset_admin_password.py --mode api --apply   --email encargado.finanzas@quantumgrupo.mx   --username MoisesFinanzas   --new-password 'NuevaClaveSegura!2026'
```
