---
name: adr-writer
description: Redactar un Architecture Decision Record (ADR) nuevo o evaluar alternativas arquitectónicas estructurales para una decisión difícil de revertir. Usar cuando el usuario pida documentar una decisión de arquitectura, crear/escribir un ADR, comparar opciones de diseño estructural (p. ej. elegir entre dos tecnologías, patrones o topologías de componentes) o registrar el reemplazo de un ADR existente. No usar para documentar requisitos funcionales (eso es spec.md) ni planes de tareas de implementación (eso es plan.md).
---

# adr-writer

## Propósito

Producir Architecture Decision Records (ADR) consistentes, atómicos y auditables,
reutilizando siempre la plantilla del proyecto (`docs/adr/000-template.md`) y sin
duplicar contenido que ya vive en otros documentos del repositorio (`spec.md`,
`plan.md`). Un ADR es un registro histórico de **por qué** se tomó una decisión
estructural, no un manual de implementación ni una lista de requisitos.

## Cuándo usar esta Skill

Invocar esta Skill cuando el usuario:
- Pida "crear un ADR", "documentar esta decisión de arquitectura" o "escribir un ADR para X".
- Esté evaluando alternativas estructurales difíciles de revertir (elegir un motor de
  persistencia, un protocolo de comunicación entre servicios, un patrón de
  concurrencia, una topología de despliegue, etc.).
- Necesite reemplazar o superar un ADR previo porque la decisión cambió.

**No** invocar esta Skill para:
- Escribir o editar escenarios BDD o criterios de aceptación → eso pertenece a `spec.md`.
- Listar archivos a modificar o tareas de implementación → eso pertenece a `plan.md`.
- Decisiones triviales y fácilmente reversibles (nombrar una variable, elegir un
  formato de log). Un ADR solo documenta decisiones estructurales de alto costo de
  reversión.

## Flujo de ejecución

1. **Leer la plantilla obligatoria.** Antes de escribir una sola línea, leer
   `docs/adr/000-template.md` completo y usar esa estructura como esqueleto literal
   del nuevo archivo. No inventar secciones nuevas ni renombrar las existentes.
2. **Confirmar que es una sola decisión.** Si el usuario describe más de una decisión
   estructural independiente, separarlas en ADRs distintos antes de redactar. No
   mezclar dos decisiones en un mismo archivo aunque estén relacionadas.
3. **Revisar el historial de ADRs existentes** (`docs/adr/NNN-*.md`) para:
   - Detectar el siguiente número secuencial disponible.
   - Verificar si este ADR reemplaza a uno anterior (y en ese caso, planear la
     actualización de metadatos de ambos lados: "Reemplaza a" / "Reemplazado por").
4. **Investigar y redactar al menos 2 opciones reales** con ventajas y desventajas
   genuinas (ver Reglas estrictas, sección 3). Si el usuario solo propuso una opción,
   preguntar o investigar activamente cuál sería la alternativa real más competitiva
   antes de continuar — nunca rellenar con una opción débil solo para cumplir el mínimo.
5. **Redactar el ADR completo** siguiendo exactamente las 4 secciones de la plantilla
   (Contexto y Problema, Opciones Consideradas, Decisión Arquitectónica, Consecuencias
   y Trade-offs) y los metadatos permitidos.
6. **Aplicar el checklist de validación** (abajo) antes de guardar el archivo.
7. **Guardar como archivo nuevo** en `docs/adr/NNN-slug-descriptivo.md` (nunca editar
   un ADR histórico ya aceptado — ver Reglas estrictas, sección 2).

## Reglas estrictas (no negociables)

### 1. Uso de plantilla y metadatos
- Leer y reutilizar **obligatoriamente** la estructura de `docs/adr/000-template.md`.
- Los metadatos del encabezado se limitan **estrictamente** a: `Estado`, `Fecha`,
  `Autor(es)` y `Reemplaza a` / `Reemplazado por`. No agregar campos adicionales
  (por ejemplo, "Prioridad", "Revisores", "Tags").
- **Prohibido** incluir una sección "Componentes Afectados" o equivalente con enlaces
  frágiles a rutas de código (`src/...`, `tests/...`) o viñetas tácticas de comandos
  a ejecutar. Esas rutas y comandos cambian con el código; el ADR documenta la
  decisión, no el estado actual del árbol de archivos.

### 2. Atomicidad e inmutabilidad
- Documentar **exactamente 1 sola decisión arquitectónica estructural y difícil de
  revertir** por archivo. Si aparece una segunda decisión independiente, se separa en
  otro ADR.
- Tratar los ADRs como un registro **append-only**: nunca modificar el contenido de
  una decisión histórica ya aceptada. Si una decisión aceptada cambia, se crea un
  **ADR nuevo** que la reemplaza, y se actualiza únicamente el metadato
  `Estado`/`Reemplazado por` del ADR antiguo (nunca su Contexto, Opciones o Decisión
  originales).

### 3. Análisis de alternativas
- Exigir la comparación de **al menos 2 opciones arquitectónicas reales**, cada una
  con ventajas y desventajas auténticas y verificables para el contexto del proyecto.
- **Prohibido** usar opciones de relleno o argumentos de hombre de paja (strawmen):
  toda opción descartada debe ser una alternativa que un ingeniero competente
  consideraría seriamente, no una versión débil construida solo para perder.

### 4. Diagramas Mermaid
- Los diagramas Mermaid son **opcionales**.
- Si se incluyen, deben ser **exclusivamente estructurales**: capas, límites de
  contexto o topología de componentes (p. ej. `graph` o `flowchart` mostrando cajas y
  relaciones de dependencia, no pasos de ejecución).
- **Prohibido** usar diagramas de flujo algorítmico (`if/else`, bucles) o diagramas de
  secuencia detallados con mensajes paso a paso. Eso pertenece a documentación de
  implementación, no a un ADR.

### 5. Separación de responsabilidades (anti-duplicación)
- **Prohibido** duplicar en el ADR:
  - Criterios funcionales o escenarios BDD (Given/When/Then) que ya viven o deberían
    vivir en `spec.md`.
  - Listas de archivos a modificar o tareas de implementación que ya viven o deberían
    vivir en `plan.md`.
- El ADR responde "¿qué decisión estructural se tomó y por qué?", nunca "¿qué debe
  hacer el sistema?" (eso es spec) ni "¿qué pasos de trabajo hay que seguir?" (eso es
  plan).

## Checklist de validación antes de guardar

Antes de escribir el archivo final, verificar cada punto; si alguno falla, corregir
antes de guardar:

- [ ] ¿El archivo sigue exactamente la estructura de `docs/adr/000-template.md`
      (mismas 4 secciones, mismo orden)?
- [ ] ¿Los metadatos del encabezado son únicamente `Estado`, `Fecha`, `Autor(es)` y
      `Reemplaza a`/`Reemplazado por` — sin campos adicionales?
- [ ] ¿No existe ninguna sección "Componentes Afectados" ni enlaces a rutas de código
      o comandos tácticos?
- [ ] ¿El archivo documenta exactamente **una** decisión estructural difícil de
      revertir, no varias mezcladas?
- [ ] ¿Se presentan **al menos 2 opciones reales** con ventajas/desventajas
      auténticas, sin opciones de relleno?
- [ ] ¿Si hay un diagrama Mermaid, es puramente estructural (capas/límites/topología)
      y no un flujo algorítmico o de secuencia detallado?
- [ ] ¿El ADR evita duplicar escenarios BDD de `spec.md` o listas de tareas/archivos
      de `plan.md`?
- [ ] Si este ADR reemplaza a uno anterior, ¿se actualizó el metadato del ADR antiguo
      (`Estado: Reemplazado por ADR-NNN`) sin tocar su contenido histórico?
- [ ] ¿El nombre del archivo sigue el patrón `NNN-slug-descriptivo.md` con el
      siguiente número secuencial disponible en `docs/adr/`?
