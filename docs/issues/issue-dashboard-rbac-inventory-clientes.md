# Issue: Dashboard por periodo + Validaciones presupuesto + RBAC empresa + Inventario/Clientes + Movimientos 402/403 + PDF + Fix export

## Contexto
Se requiere extender QFinance con control por periodo en dashboard, validaciones duras de presupuesto, RBAC por empresa server-side, módulos de inventario/clientes, reglas obligatorias para movimientos 402/403 y corrección del cálculo de ejecutado en exportes.

## Alcance
- Backend FastAPI: nuevos endpoints dashboard periodizado, presupuesto planificado con breakdown, inventario/clientes CRUD base, recibo PDF, fix export ejecutado.
- Frontend React: selector de periodo dashboard y captura `client_id` en movimientos 402/403.
- Tests pytest mínimos de validación, RBAC y export.

## Checklist
### Backend
- [x] Endpoints dashboard: total/mensual/trimestral/anual
- [x] Validación presupuesto total/anual/mensual (422 estructurado)
- [x] RBAC company-level en dashboard e inventario/clientes
- [x] Reglas 402/403 (cliente obligatorio, referencia forzada, saldo)
- [x] Endpoint de recibo PDF
- [x] Fix export ejecutado

### Frontend
- [x] Selector de periodo en dashboard
- [x] Captura `client_id` en flujo 402/403

### Tests
- [x] Presupuesto anual > total
- [x] Presupuesto mensual > anual
- [x] 402/403 sin cliente
- [x] 402/403 referencia forzada y ajuste saldo
- [x] RBAC cross-company
- [x] Export ejecutado suma egresos

### Deploy
- [x] Cambios backward-compatible (se agregan endpoints/campos)

## Criterios de aceptación (Given/When/Then)
- Given finanzas, When usa TODO dashboard, Then ve acumulado según filtros.
- Given usuario no global, When consulta otra empresa, Then 403.
- Given presupuesto inválido, When excede límites, Then 422 con código.
- Given 402/403 sin cliente, When crea movimiento, Then 422.
- Given 402/403 con cliente+inventario, When crea movimiento, Then referencia se fuerza y saldo baja.
- Given egresos reales, When exporta reporte, Then ejecutado no sale en 0.
