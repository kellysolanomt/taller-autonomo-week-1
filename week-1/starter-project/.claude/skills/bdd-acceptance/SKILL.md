---
name: bdd-acceptance
description: Cómo redactar escenarios BDD Given/When/Then estilo Dan North en las especificaciones (specs/NNN-*.md) con vocabulario ubicuo de negocio, y cómo mapear cada escenario 1:1 a funciones test_bdd_* en tests/ usando TestClient (FastAPI) y CliRunner (Typer) sobre almacenamiento aislado. Usar al escribir o revisar una especificación en specs/ o sus pruebas de aceptación en tests/.
---

# Escenarios BDD y pruebas de aceptación de IncidentOps

Referencia: `specs/001-triage-endpoint-manual.md` §8 (escenarios de H001) y `tests/test_spec_001_triage.py` / `tests/conftest.py` (su implementación). `AGENTS.md` fija `uv run pytest -q` como verificación primaria del feature de triaje.

Nota de estado: los cuatro escenarios existentes en `specs/001-triage-endpoint-manual.md` §8 y sus pruebas en `tests/test_spec_001_triage.py` son anteriores a la convención `test_bdd_*` descrita aquí (se llaman `test_caida_critica_http_502_...`, `test_cuenta_individual_bloqueada_...`, etc.). No los renombres solo para cumplir esta convención; aplícala a escenarios y pruebas nuevos, y a specs nuevas (`specs/002-...md` en adelante).

## 1. Cómo redactar un escenario BDD en la spec

Estilo Dan North: el escenario es una especificación ejecutable del comportamiento del negocio, no una descripción de cómo está implementado el código. Debe poder leerlo una persona de producto sin conocer Python ni el esquema de base de datos.

Formato en el Markdown de la spec, dentro de `## N. Escenarios BDD`, un bloque ```gherkin``` por escenario:

```gherkin
Given <contexto de negocio en términos del dominio: tipo de incidente, alcance, quién reporta>
When <la acción observable desde la interfaz: "se envía el reporte de triaje", "se ejecuta el comando de triaje">
Then <el resultado de negocio esperado>
And <resultados adicionales, uno por línea>
```

Reglas de vocabulario ubicuo:

- **Usa los términos del dominio y del contrato de interfaz, nunca los de la implementación interna**: `severity`, `component`, `recommended_team`, `duplicate_group_key`, códigos de estado HTTP (`200 OK`, `422 Unprocessable Entity`) y nombres de endpoint/comando son parte del contrato público (`specs/001-...md` §4/§5) y sí pueden aparecer. Esto no es lo mismo que exponer detalle interno.
- **Prohibido en un escenario**: nombres de clases o módulos Python (`IncidentService`, `TriageResult`, `src.domain.triage_rules`), nombres de tablas o columnas SQL, nombres de fixtures de pytest (`api_client`, `cli_runner`), detalles de `sqlite3` o del motor de persistencia, y cualquier referencia a cómo está organizado el código fuente.
- Si una regla de negocio necesita justificarse (por qué un valor se mantiene así y no de otra forma), documéntala en una nota fuera del bloque `gherkin` — como ya hace el Escenario 1 de `specs/001-...md` — no la metas dentro del Given/When/Then.
- Cada escenario es independiente y autocontenible: no asume el orden de ejecución de otro escenario ni estado dejado por uno anterior.
- Numera y titula los escenarios de forma descriptiva del caso de negocio (`### Escenario N: <qué situación de negocio cubre>`), igual que los cuatro existentes.
- Casos borde que no ameritan su propio escenario `gherkin` completo van en la tabla de `## Casos borde y criterios de aceptación adicionales` (ver §9 de `specs/001-...md`), no inflando la lista de escenarios BDD.

## 2. Mapeo 1:1 escenario → función de prueba

Por cada escenario `### Escenario N: <título>` en la spec debe existir **exactamente una** función de prueba en `tests/test_spec_NNN_<feature>.py`, sin fusionar ni partir escenarios entre funciones.

Convención de nombre: `test_bdd_<slug_del_escenario_en_espanol>`, donde `<slug>` resume el Given en snake_case (p. ej. `test_bdd_caida_critica_http_502_en_pasarela_de_pagos`, `test_bdd_paridad_en_cli`). El docstring de la función reproduce el Given/When/Then en prosa, como ya hacen las pruebas actuales.

Estructura de la función:

```python
def test_bdd_<slug>(api_client, ...):
    """
    Given <mismo contexto que en la spec>,
    When <misma acción>,
    Then <mismo resultado>.
    """
    # Given: construir la solicitud de negocio (payload HTTP o argumentos CLI)
    ...
    # When: invocar la única interfaz que el escenario ejercita
    response = api_client.post(ENDPOINT, json={...})
    # Then: aserciones sobre el resultado de negocio, en el mismo vocabulario de la spec
    assert response.status_code == 200
    assert response.json()["severity"] == "P0"
```

- **Adaptador REST**: usa la fixture `api_client` (`fastapi.testclient.TestClient` construido sobre `create_app()`, ver `tests/conftest.py`). Nunca instancies `TestClient` dentro del test; reutiliza la fixture.
- **Adaptador CLI**: usa las fixtures `cli_runner` (`typer.testing.CliRunner`) y `cli_app_under_test` (la app Typer real). Invoca con `cli_runner.invoke(cli_app_under_test, [...])` y verifica `result.exit_code` y `result.stdout`/`stderr`, igual que `test_paridad_en_cli`.
- Si el mismo escenario de negocio debe verificarse en ambas interfaces (paridad REST/CLI, ver skill `hexagonal-architecture`), son dos funciones de prueba (`test_bdd_<slug>_api` y `test_bdd_<slug>_cli`, o una función de paridad dedicada como `test_bdd_paridad_en_cli`), no una sola función con ramas condicionales por interfaz.
- Las aserciones leen los mismos campos que el Then de la spec (`severity`, `recommended_team`, `duplicate_group_key`, código de salida, clave `"error"`); si una aserción necesita un dato que no está en el escenario de la spec, falta algo en la spec, no en la prueba.

### Almacenamiento aislado

El feature de triaje (H001) no persiste estado: cada request es independiente y una repetición idéntica produce la misma respuesta (`specs/001-...md` §9). Para features futuras que sí toquen persistencia (repositorio de incidentes, SQLite u otro motor):

- Cada función `test_bdd_*` obtiene su propia instancia de almacenamiento mediante una fixture dedicada (p. ej. una conexión `sqlite3` en memoria o un archivo temporal por test vía `tmp_path`), nunca una instancia global compartida entre pruebas ni el archivo de datos real del proyecto.
- La fixture de almacenamiento se inyecta en la construcción del `api_client`/`cli_app_under_test` de ese test (composition root de prueba), igual que `create_app()` ya permite inyectar dependencias en producción; no se parchea almacenamiento con mocks que reemplacen la lógica del adaptador de salida.
- Ninguna prueba depende del orden de ejecución ni dejar datos para la siguiente; `pytest` debe poder ejecutar cada `test_bdd_*` de forma aislada (`uv run pytest -q tests/test_spec_NNN_feature.py::test_bdd_<slug>`) con el mismo resultado que la suite completa.

## Checklist rápido

1. ¿El bloque `gherkin` usa solo vocabulario de negocio/contrato de interfaz, sin clases Python ni tablas SQL?
2. ¿Existe una función `test_bdd_*` por cada escenario de la spec, ni más ni menos?
3. ¿La prueba usa `api_client`/`cli_runner` + `cli_app_under_test` en vez de instanciar el framework a mano?
4. Si el feature persiste estado, ¿cada prueba usa almacenamiento propio y aislado, sin compartir instancia ni orden de ejecución?
5. ¿`uv run pytest -q` pasa con la nueva prueba incluida?
