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

## Semáforo de Cumplimiento

- 🟢 **Verde**: Ejercido ≤ 90% del presupuesto
- 🟡 **Amarillo**: Ejercido entre 90% y 100%
- 🔴 **Rojo**: Ejercido > 100% (requiere autorización)
