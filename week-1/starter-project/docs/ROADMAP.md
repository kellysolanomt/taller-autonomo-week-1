# Roadmap — IncidentOps

Hoja de ruta de producto y operaciones. Los hitos se presentan en orden de evolución; el alcance de cada uno puede ajustarse según lo que se aclare en su momento.

## H001 — Triaje multi-interfaz

- **Objetivo:** Exponer la clasificación y el enrutamiento determinista de reportes como servicio HTTP y comando CLI, sin persistencia, para consumo inmediato desde web y terminal.
- **Resultados esperados:** Un reporte entrante obtiene la misma clasificación y destino sin importar la interfaz; `POST /api/v1/incidents/triage` y el comando `triage --incident-id ... --raw-text ...` comparten el mismo caso de uso; el resultado está disponible al instante y no deja estado almacenado.
- **Especificación:** `specs/001-triage-endpoint-manual.md`.
- **Fuera de alcance:** Guardar los reportes o sus resultados, historial de clasificaciones, edición manual de reglas, autenticación, procesamiento por lote y adaptador MCP.

## H002 — Resumen de incidentes activos

- **Objetivo:** Permitir consultar los incidentes actualmente activos, los incumplimientos de SLA y el filtrado por componente desde web y terminal.
- **Resultados esperados:** Una vista consolidada de incidentes activos, con incumplimientos de SLA visibles y filtrado por componente, consistente entre interfaces.
- **Fuera de alcance:** Crear o modificar incidentes desde el resumen, notificaciones automáticas, exportación de reportes y contratos o rutas de interfaz aún no definidos.

## H003 — Ciclo de vida, duplicados y SLA

- **Objetivo:** Registrar incidentes entrantes de forma persistente, alertar cuando ya exista otro equivalente abierto y auditar su SLA en cualquier instante de referencia, con el mismo comportamiento disponible desde la API HTTP y desde la herramienta CLI.
- **Resultados esperados:** Los incidentes quedan registrados y consultables en el tiempo; los duplicados abiertos se señalan al ingresar uno nuevo; el estado de SLA puede evaluarse para cualquier instante de referencia; estas tres capacidades se comportan de forma idéntica tanto por la API HTTP como desde el CLI.
- **Fuera de alcance:** Fusión automática de duplicados, escalamiento o reasignación automática, edición del historial de incidentes y políticas de retención o archivado.

## H004 — Persistencia relacional dedicada y runtime en contenedores

- **Objetivo:** Preparar el servicio para una ejecución reproducible en contenedores, con una base de datos relacional dedicada y un chequeo real de conectividad operativa.
- **Resultados esperados:** El servicio arranca de forma reproducible en contenedores, opera contra su base de datos dedicada y reporta de forma fiable si la conectividad con ella es operativa.
- **Fuera de alcance:** Alta disponibilidad, replicación o respaldo automatizado, orquestación multi-entorno, monitoreo avanzado y contratos o rutas de interfaz aún no definidos.
