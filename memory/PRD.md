# QFinance - Control Presupuestal Multiempresa

## Descripción del Producto
Sistema de control financiero y presupuestal para desarrollos inmobiliarios. Permite gestionar presupuestos, movimientos y reportes para múltiples empresas y proyectos con semáforo de cumplimiento y soporte multi-moneda (MXN/USD).

## Stack Tecnológico
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Base de datos**: MongoDB
- **Preparado para**: Migración a Postgres + Node/Express

## Reglas Clave (NO NEGOCIABLES)
1. "QFinance" es SOLO marca/UI. NO renombrar "Grupo Q" en BD/catálogos
2. TZ: UTC en BD, mostrar en America/Tijuana
3. Monedas: MXN y USD. USD requiere tipo_cambio obligatorio
4. Semáforo: Verde ≤90%, Amarillo 90-100%, Rojo >100%
5. Exceso >100% requiere Autorizador
6. Roles: Admin, Finanzas, Autorizador, Solo-lectura

## Empresas Configuradas
1. Altitud 3
2. Terraviva Desarrollos
3. Grupo Q

## Usuarios Demo
| Email | Contraseña | Rol |
|-------|------------|-----|
| admin@finrealty.com | admin123 | Administrador |
| finanzas@finrealty.com | finanzas123 | Finanzas |
| autorizador@finrealty.com | auth123 | Autorizador |
| lectura@finrealty.com | lectura123 | Solo Lectura |

---

## Estado de Implementación

### ✅ Hito 1 - COMPLETO
- Arquitectura + OpenAPI/Swagger + esquemas

### ✅ Hito 2 Entrega A - COMPLETO
- Dashboard con KPIs en tiempo real
- Reportes con detalle por partida y drilldown
- Filtros: Empresa, Proyecto, Mes, Moneda
- Datos demo: 2 proyectos, 6 partidas, 15 proveedores, 200 movimientos, 3 meses

### ✅ Multiempresa + Catálogo - COMPLETO
- Colección `empresas` con 3 empresas
- `proyectos.empresa_id` obligatorio
- Colección `catalogo_partidas` como source of truth
- Endpoints: /api/empresas, /api/catalogo-partidas

### ✅ Rebranding UI (P0) - COMPLETO (11-Feb-2025)
- Marca "FinRealty" → "QFinance" en toda la UI
- Logo corporativo Quantum integrado como overlay en login
- Logo en sidebar del dashboard
- Favicon actualizado
- README.md actualizado
- Foto del edificio en login MANTENIDA intacta

### ✅ Entrega B: Import/Export (P1) - COMPLETO (11-Feb-2025)

**Import CSV (/api/movements/import-csv)**
- Columnas exactas: fecha, empresa, proyecto, partida, proveedor, moneda, monto, tipo_cambio, referencia, descripcion
- Validaciones bloqueantes por fila:
  - ✅ empresa existe y activa
  - ✅ proyecto existe, activo y pertenece a empresa
  - ✅ partida existe y activa en catalogo_partidas
  - ✅ monto > 0
  - ✅ moneda ∈ {MXN, USD}
  - ✅ USD requiere tipo_cambio obligatorio
  - ✅ fecha sin hora → interpreta America/Tijuana, guarda UTC
- Detección duplicados: fecha+empresa+proyecto+proveedor+monto+referencia
- Response: total_filas, insertadas, rechazadas, duplicadas_omitidas + errores por fila

**Export Excel (/api/reports/export-data)**
- Hoja 1 "Resumen": KPIs filtrados
- Hoja 2 "Detalle": por partida + semáforo
- Fechas en America/Tijuana
- Refleja filtros aplicados en UI

**Audit Log (/api/import-export-logs)**
- Import: inicio/fin, usuario, timestamp, conteos, errores resumen
- Export: usuario, timestamp, filtros usados

**Frontend UI**
- Dialog de Import CSV con plantilla descargable
- Visualización de resultados (insertadas/rechazadas/duplicadas)
- Lista de errores por fila con columna y motivo
- Botón Export Excel mejorado

---

## Próximas Tareas

### 🟡 P2 - Flujo de Autorizaciones
- Workflow para excesos >100%
- Aprobación/rechazo por Autorizador
- Historial de autorizaciones

### 🟢 P3 - RBAC y Auditoría Completa
- Gestión completa de roles
- Audit trail detallado
- Permisos granulares

---

## Archivos Clave
- `/app/frontend/src/pages/Login.js` - Login con branding QFinance
- `/app/frontend/src/components/DashboardLayout.js` - Layout con logo
- `/app/frontend/public/brand/quantum_logo.jpg` - Logo corporativo
- `/app/frontend/public/index.html` - Título y favicon
- `/app/backend/server.py` - API principal

## Catálogo de Partidas (NO MODIFICAR)
```
100 COSTO DIRECTO
101 TERRENO
102 PROYECTOS
103 LICENCIAS Y PERMISOS
104 EDIFICACION
105 URBANIZACION
106 INDIRECTOS DE OBRA
107 ACCESO
108 AMENIDADES
109 OFICINAS DE VENTAS
110 IMPREVISTOS
111 OBRAS CABECERAS
200 GASTOS DE VENTA Y ADMINISTRACION
201 GASTOS DE PUBLICIDAD Y PROMOCION
202 ACONDICIONAMIENTO DE MUESTRAS
203 COMISIONES SOBRE VENTA
204 DIRECCION DE PROYECTO
205 GASTOS ADMINISTRATIVOS
206 DOCUM TECNICA
207 GARANTIAS Y POSTVENTA
300 GASTOS FINANCIEROS
301 COMISIONES BANCARIAS
302 INTERESES
303 AMORTIZACION
400 INGRESOS
401 PRESTAMOS SOCIOS
402 ENGANCHES
403 INDIVIDUALIZACION
404 CREDITOS
```
