# FinRealty - Sistema de Control Financiero Inmobiliario

## Hito 1: Plan + OpenAPI + Esquema BD + Criterios de Aceptación

---

## 1. ARQUITECTURA GENERAL

### Stack Actual (MVP)
```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│                    React + Tailwind CSS                         │
│                    Puerto: 3000                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND                                   │
│                    FastAPI (Python)                             │
│                    Puerto: 8001                                  │
│                    Prefijo: /api/*                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATABASE                                  │
│                       MongoDB                                    │
│                    Puerto: 27017                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Preparación para Migración (Postgres + Node/Express)
- Contrato REST congelado (OpenAPI 3.0)
- Service/Repository layer separado
- Sin dependencias específicas de MongoDB en lógica de negocio
- Variables de entorno preparadas: `DB_PROVIDER`, `DATABASE_URL`

---

## 2. ESQUEMA DE BASE DE DATOS

### Colecciones MongoDB (→ Tablas Postgres)

#### users
```json
{
  "id": "uuid",
  "email": "string (unique, indexed)",
  "name": "string",
  "role": "enum: admin|finanzas|autorizador|solo_lectura",
  "password_hash": "string",
  "is_active": "boolean",
  "created_at": "datetime (UTC)"
}
```

#### projects
```json
{
  "id": "uuid",
  "code": "string (unique, indexed)",
  "name": "string",
  "description": "string|null",
  "is_active": "boolean",
  "created_at": "datetime (UTC)"
}
```

#### partidas
```json
{
  "id": "uuid",
  "code": "string (unique, indexed)",
  "name": "string",
  "description": "string|null",
  "is_active": "boolean",
  "created_at": "datetime (UTC)"
}
```

#### providers
```json
{
  "id": "uuid",
  "code": "string (unique, indexed)",
  "name": "string",
  "rfc": "string|null",
  "is_active": "boolean",
  "created_at": "datetime (UTC)"
}
```

#### budgets
```json
{
  "id": "uuid",
  "project_id": "uuid (FK → projects)",
  "partida_id": "uuid (FK → partidas)",
  "year": "integer",
  "month": "integer (1-12)",
  "amount_mxn": "decimal",
  "notes": "string|null",
  "created_by": "uuid (FK → users)",
  "created_at": "datetime (UTC)"
}
// Índice único: (project_id, partida_id, year, month)
```

#### movements
```json
{
  "id": "uuid",
  "project_id": "uuid (FK → projects)",
  "partida_id": "uuid (FK → partidas)",
  "provider_id": "uuid (FK → providers)",
  "date": "datetime (UTC)",
  "currency": "enum: MXN|USD",
  "amount_original": "decimal",
  "exchange_rate": "decimal",
  "amount_mxn": "decimal (calculado)",
  "reference": "string",
  "description": "string|null",
  "status": "enum: normal|pending_authorization|authorized|rejected",
  "authorization_id": "uuid|null (FK → authorizations)",
  "created_by": "uuid (FK → users)",
  "created_at": "datetime (UTC)"
}
// Índice único para duplicados: (date, provider_id, amount_original, reference)
```

#### authorizations
```json
{
  "id": "uuid",
  "movement_id": "uuid|null (FK → movements)",
  "reason": "string",
  "requested_by": "uuid (FK → users)",
  "status": "enum: pending|approved|rejected",
  "resolved_at": "datetime|null (UTC)",
  "resolved_by": "uuid|null (FK → users)",
  "notes": "string|null",
  "created_at": "datetime (UTC)"
}
```

#### exchange_rates
```json
{
  "id": "uuid",
  "date": "string (YYYY-MM-DD, indexed)",
  "rate": "decimal",
  "created_at": "datetime (UTC)"
}
```

#### audit_logs
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "user_email": "string",
  "user_role": "string",
  "action": "enum: CREATE|UPDATE|DELETE|IMPORT|RESOLVE",
  "entity": "string",
  "entity_id": "string",
  "changes": "json",
  "timestamp": "datetime (UTC)"
}
// Índice: (entity, entity_id), (timestamp DESC)
```

#### config
```json
{
  "id": "uuid",
  "key": "string (unique)",
  "value": "any",
  "updated_at": "datetime (UTC)",
  "updated_by": "uuid"
}
```

---

## 3. CONTRATO REST API (OpenAPI 3.0)

### Base URL: `/api`

### Autenticación
- JWT Bearer Token
- Header: `Authorization: Bearer <token>`
- Expiración: 7 días

### Endpoints

#### Auth
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | /auth/register | Registrar usuario | Público |
| POST | /auth/login | Iniciar sesión | Público |
| GET | /auth/me | Usuario actual | Autenticado |

#### Catálogos
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /projects | Listar proyectos | Todos |
| POST | /projects | Crear proyecto | Admin |
| PUT | /projects/{id} | Actualizar proyecto | Admin |
| GET | /partidas | Listar partidas | Todos |
| POST | /partidas | Crear partida | Admin |
| PUT | /partidas/{id} | Actualizar partida | Admin |
| GET | /providers | Listar proveedores | Todos |
| POST | /providers | Crear proveedor | Admin |
| PUT | /providers/{id} | Actualizar proveedor | Admin |

#### Presupuestos
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /budgets | Listar presupuestos | Todos |
| POST | /budgets | Crear presupuesto | Admin, Finanzas |
| PUT | /budgets/{id} | Actualizar presupuesto | Admin, Finanzas |
| DELETE | /budgets/{id} | Eliminar presupuesto | Admin |

#### Movimientos
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /movements | Listar movimientos | Todos |
| POST | /movements | Crear movimiento | Admin, Finanzas |
| POST | /movements/import | Importar CSV | Admin, Finanzas |

#### Autorizaciones
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /authorizations | Listar autorizaciones | Todos |
| PUT | /authorizations/{id} | Resolver autorización | Admin, Autorizador |

#### Reportes
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /reports/dashboard | KPIs y resumen | Todos |
| GET | /reports/partida-detail/{id} | Detalle de partida | Todos |

#### Tipos de Cambio
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /exchange-rates | Listar tipos de cambio | Todos |
| POST | /exchange-rates | Crear/actualizar tipo | Admin, Finanzas |

#### Auditoría
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /audit-logs | Listar bitácora | Admin, Autorizador |

#### Configuración
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /config | Obtener configuración | Todos |
| PUT | /config/{key} | Actualizar config | Admin |

#### Usuarios
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| GET | /users | Listar usuarios | Admin |
| PUT | /users/{id} | Actualizar usuario | Admin |

#### Utilidades
| Método | Ruta | Descripción | Roles |
|--------|------|-------------|-------|
| POST | /seed-demo-data | Cargar datos demo | Público |

---

## 4. REGLAS DE NEGOCIO

### Semáforo Presupuestal
```
Verde:    % avance ≤ 90%
Amarillo: 90% < % avance ≤ 100%
Rojo:     % avance > 100%
```

### Autorización Requerida
Se genera autorización pendiente cuando:
1. Presupuesto = $0 (partida sin presupuesto definido)
2. Nuevo gasto causa exceso (>100% del presupuesto)

### Validación de Movimientos
1. Proyecto debe existir y estar activo
2. Partida debe existir y estar activa
3. Proveedor debe existir y estar activo
4. Monto > 0
5. Fecha válida
6. Si moneda = USD, debe existir tipo de cambio para la fecha

### Detección de Duplicados
Llave única: `(fecha, proveedor_id, monto_original, referencia)`

### Zona Horaria
- Almacenamiento: UTC
- Visualización: America/Tijuana (Pacífico)
- Import CSV: fechas sin hora se interpretan como America/Tijuana

---

## 5. RBAC - Control de Acceso por Rol

| Permiso | Admin | Finanzas | Autorizador | Solo Lectura |
|---------|-------|----------|-------------|--------------|
| Ver dashboard | ✅ | ✅ | ✅ | ✅ |
| Ver reportes | ✅ | ✅ | ✅ | ✅ |
| Exportar | ✅ | ✅ | ✅ | ✅ |
| Crear/editar presupuestos | ✅ | ✅ | ❌ | ❌ |
| Crear movimientos | ✅ | ✅ | ❌ | ❌ |
| Importar CSV | ✅ | ✅ | ❌ | ❌ |
| Aprobar/rechazar | ✅ | ❌ | ✅ | ❌ |
| Gestionar catálogos | ✅ | ❌ | ❌ | ❌ |
| Gestionar usuarios | ✅ | ❌ | ❌ | ❌ |
| Ver bitácora | ✅ | ❌ | ✅ | ❌ |
| Configuración | ✅ | ❌ | ❌ | ❌ |

---

## 6. CRITERIOS DE ACEPTACIÓN

### Hito 1 (Actual) ✅
- [x] Arquitectura documentada
- [x] Esquema de BD definido
- [x] Contrato REST (OpenAPI) congelado
- [x] Reglas de negocio documentadas
- [x] RBAC definido

### Hito 2: Implementación con datos demo
- [ ] Backend funcionando con todos los endpoints
- [ ] Frontend con todas las pantallas navegables
- [ ] Datos demo cargados (4 proyectos, 6 partidas, 6 proveedores)
- [ ] Semáforo funcionando correctamente
- [ ] Filtros por proyecto/mes/año operativos
- [ ] KPIs calculando correctamente

### Hito 3: RBAC + Audit Log + Import/Export
- [ ] Login funcional con 4 roles
- [ ] Permisos validados en backend Y frontend
- [ ] Audit log registrando todas las acciones
- [ ] Import CSV con validación completa
- [ ] Reporte de errores en import
- [ ] Export a Excel funcional
- [ ] Flujo de autorización completo

---

## 7. USUARIOS DEMO

| Email | Contraseña | Rol |
|-------|------------|-----|
| admin@finrealty.com | admin123 | Admin |
| finanzas@finrealty.com | finanzas123 | Finanzas |
| autorizador@finrealty.com | auth123 | Autorizador |
| lectura@finrealty.com | lectura123 | Solo Lectura |

---

## 8. VARIABLES DE ENTORNO

### Backend (.env)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
JWT_SECRET=finrealty-secret-key-2024-mvp
CORS_ORIGINS=*
# Preparadas para migración:
# DB_PROVIDER=postgres
# DATABASE_URL=postgresql://...
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=https://[app].preview.emergentagent.com
```

---

## 9. FORMATO CSV PARA IMPORT

### Columnas requeridas
```csv
fecha,proyecto,partida,proveedor,moneda,monto,referencia,descripcion
2025-01-15,TORRE-A,CONST,CEMEX,MXN,150000,FAC-001,Concreto premezclado
2025-01-16,TORRE-A,ELEC,ELECT,USD,5000,FAC-002,Material eléctrico
```

### Validaciones
1. `fecha`: formato YYYY-MM-DD
2. `proyecto`: código existente en catálogo
3. `partida`: código existente en catálogo
4. `proveedor`: código existente en catálogo
5. `moneda`: MXN o USD
6. `monto`: número > 0
7. `referencia`: obligatorio, parte de llave única
8. `descripcion`: opcional

### Errores bloqueantes
- Proyecto/partida/proveedor no encontrado
- Moneda inválida
- Monto ≤ 0
- Fecha inválida
- Tipo de cambio faltante (para USD)
- Duplicado detectado

---

## Próximo: Hito 2 - Implementación funcionando con datos demo

¿Confirmas para proceder con el Hito 2?
