"""Pruebas de aceptación BDD del Hito H002 (resumen de incidentes activos).

Escenarios tomados de `specs/002-active-incidents-summary/spec.md`, ejecutados contra
los adaptadores reales (API vía `TestClient`, CLI vía `CliRunner`), ambos delegando en
el mismo `IncidentService`, sobre un `SQLiteIncidentRepository` en memoria nuevo y
aislado por prueba (fixtures `incident_repository`/`incident_service`/
`summary_api_client`/`summary_cli_app` de `tests/conftest.py`).
"""

import json
import time
from datetime import datetime

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.domain.models import Incident

SUMMARY_ENDPOINT = "/api/v1/incidents/summary"


def _incident(
    incident_id: str,
    component: str,
    severity: str,
    status: str,
    created_at: datetime,
    resolved_at: datetime | None = None,
) -> Incident:
    return Incident(
        incident_id=incident_id,
        title=f"Incidente {incident_id}",
        component=component,
        severity=severity,
        status=status,
        created_at=created_at,
        resolved_at=resolved_at,
    )


# --- Historia de Usuario 1: resumen por HTTP (P1) -----------------------------------


def test_bdd_resumen_http_incluye_incumplimientos_y_excluye_resueltos(
    summary_api_client, incident_repository
):
    """
    Given incidentes activos con y sin incumplimiento de SLA, y un incidente resuelto,
    When se consulta el resumen por HTTP sin filtro,
    Then la respuesta indica el total activo, los incumplimientos y el detalle, sin
         incluir el incidente resuelto.
    """
    incident_repository.save_incident(
        _incident("INC-A", "payments-gateway", "P2", "OPEN", datetime(2026, 11, 23, 8, 0, 0))
    )
    incident_repository.save_incident(
        _incident(
            "INC-B", "reporting-api", "P2", "IN_PROGRESS", datetime(2026, 11, 23, 15, 0, 0)
        )
    )
    incident_repository.save_incident(
        _incident(
            "INC-C",
            "payments-gateway",
            "P1",
            "RESOLVED",
            datetime(2026, 11, 23, 8, 0, 0),
            resolved_at=datetime(2026, 11, 23, 8, 30, 0),
        )
    )

    response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T17:00:00"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 2
    assert body["breached_count"] == 1
    returned_ids = {item["incident_id"] for item in body["incidents"]}
    assert returned_ids == {"INC-A", "INC-B"}
    assert "INC-C" not in returned_ids


def test_bdd_resumen_http_vacio_sin_incidentes_activos(summary_api_client):
    """
    Given que no existe ningún incidente en estado OPEN o IN_PROGRESS,
    When se consulta el resumen por HTTP (sin indicar `reference_time`, ejercitando el
         valor por defecto "instante de la consulta" de FR-013),
    Then la respuesta es válida con el total activo en cero y el detalle vacío.
    """
    response = summary_api_client.get(SUMMARY_ENDPOINT)

    assert response.status_code == 200
    body = response.json()
    assert body == {"total_active": 0, "breached_count": 0, "incidents": []}


def test_bdd_incidente_vencido_se_cuenta_como_incumplimiento_http(
    summary_api_client, incident_repository
):
    """
    Given un incidente activo cuyo tiempo transcurrido ya superó el máximo de su SLA,
    When se consulta el resumen por HTTP,
    Then ese incidente se cuenta dentro de los incumplimientos y su detalle lo refleja
         (`requires_escalation: true`).
    """
    incident_repository.save_incident(
        _incident("INC-X", "database-cluster", "P0", "OPEN", datetime(2026, 11, 23, 10, 0, 0))
    )

    response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T11:30:00"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 1
    assert body["breached_count"] == 1
    assert body["incidents"][0]["incident_id"] == "INC-X"
    assert body["incidents"][0]["requires_escalation"] is True


# --- Historia de Usuario 2: resumen por CLI (P2) -------------------------------------


def test_bdd_paridad_resumen_http_cli_mismo_conjunto(
    summary_api_client, summary_cli_app, cli_runner, incident_repository
):
    """
    Given el mismo conjunto de incidentes activos,
    When se consulta el resumen por HTTP y por CLI sin filtro,
    Then el total activo, los incumplimientos y el detalle son idénticos en ambas.
    """
    incident_repository.save_incident(
        _incident("INC-A", "payments-gateway", "P2", "OPEN", datetime(2026, 11, 23, 8, 0, 0))
    )
    incident_repository.save_incident(
        _incident(
            "INC-B", "reporting-api", "P2", "IN_PROGRESS", datetime(2026, 11, 23, 15, 0, 0)
        )
    )

    http_response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T17:00:00"}
    )
    cli_result = cli_runner.invoke(
        summary_cli_app,
        ["summary", "--reference-time", "2026-11-23T17:00:00"],
    )

    assert http_response.status_code == 200
    assert cli_result.exit_code == 0
    http_body = http_response.json()
    cli_body = json.loads(cli_result.stdout)
    assert http_body["total_active"] == cli_body["total_active"]
    assert http_body["breached_count"] == cli_body["breached_count"]
    http_ids = sorted(item["incident_id"] for item in http_body["incidents"])
    cli_ids = sorted(item["incident_id"] for item in cli_body["incidents"])
    assert http_ids == cli_ids == ["INC-A", "INC-B"]


def test_bdd_resumen_cli_vacio_sin_incidentes_activos(summary_cli_app, cli_runner):
    """
    Given que no existe ningún incidente activo,
    When se ejecuta el comando `summary` en la terminal,
    Then la salida indica el resumen vacío y el proceso termina con código 0.
    """
    result = cli_runner.invoke(summary_cli_app, ["summary"])

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body == {"total_active": 0, "breached_count": 0, "incidents": []}


# --- Historia de Usuario 3: filtro por componente (P3) -------------------------------


def test_bdd_filtro_por_componente_limita_resumen(summary_api_client, incident_repository):
    """
    Given incidentes activos de varios componentes distintos,
    When se consulta el resumen filtrando por uno de esos componentes,
    Then el total, los incumplimientos y el detalle solo incluyen ese componente.
    """
    incident_repository.save_incident(
        _incident("INC-A", "payments-gateway", "P2", "OPEN", datetime(2026, 11, 23, 15, 0, 0))
    )
    incident_repository.save_incident(
        _incident(
            "INC-B", "reporting-api", "P2", "IN_PROGRESS", datetime(2026, 11, 23, 15, 0, 0)
        )
    )

    response = summary_api_client.get(
        SUMMARY_ENDPOINT,
        params={"component": "payments-gateway", "reference_time": "2026-11-23T17:00:00"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_active"] == 1
    assert body["incidents"][0]["incident_id"] == "INC-A"
    assert all(item["component"] == "payments-gateway" for item in body["incidents"])


def test_bdd_filtro_componente_sin_incidentes_activos(summary_api_client, incident_repository):
    """
    Given un componente sin ningún incidente activo (aunque sí tenga uno resuelto),
    When se consulta el resumen filtrando por ese componente,
    Then la respuesta es válida con el total en cero y el detalle vacío.
    """
    incident_repository.save_incident(
        _incident(
            "INC-R",
            "frontend-ui",
            "P3",
            "RESOLVED",
            datetime(2026, 11, 23, 8, 0, 0),
            resolved_at=datetime(2026, 11, 23, 8, 30, 0),
        )
    )

    response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"component": "frontend-ui"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"total_active": 0, "breached_count": 0, "incidents": []}


def test_bdd_sin_filtro_incluye_todos_los_componentes(summary_api_client, incident_repository):
    """
    Given incidentes activos de varios componentes,
    When se consulta el resumen sin indicar ningún componente,
    Then se incluyen los incidentes activos de todos los componentes.
    """
    incident_repository.save_incident(
        _incident("INC-A", "payments-gateway", "P2", "OPEN", datetime(2026, 11, 23, 15, 0, 0))
    )
    incident_repository.save_incident(
        _incident(
            "INC-B", "reporting-api", "P2", "IN_PROGRESS", datetime(2026, 11, 23, 15, 0, 0)
        )
    )

    response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T17:00:00"}
    )

    assert response.status_code == 200
    body = response.json()
    returned_components = {item["component"] for item in body["incidents"]}
    assert returned_components == {"payments-gateway", "reporting-api"}


# --- Polish: cumplimiento del puerto, solo-lectura y rendimiento --------------------


def test_bdd_sqlite_incident_repository_cumple_el_puerto():
    """
    Given el adaptador de salida `SQLiteIncidentRepository`,
    Then cumple estructuralmente el contrato `IncidentRepositoryPort` (Protocol runtime-checkable).
    """
    repo = SQLiteIncidentRepository(":memory:")

    assert isinstance(repo, IncidentRepositoryPort)
    assert repo.list_active_incidents() == []
    assert repo.get_incident("no-existe") is None
    assert repo.find_open_duplicates("payments-gateway", "outage") == []
    assert repo.check_health() is True


def test_bdd_resumen_es_solo_lectura_sin_efectos_secundarios(
    summary_api_client, summary_cli_app, cli_runner, incident_repository
):
    """
    Given incidentes activos ya sembrados,
    When se consulta el resumen dos veces (una por HTTP y una por CLI),
    Then ninguna de las dos consultas crea, modifica ni cierra incidentes (FR-011), y
         ambas producen el mismo resultado (FR-012).
    """
    incident_repository.save_incident(
        _incident("INC-A", "payments-gateway", "P2", "OPEN", datetime(2026, 11, 23, 15, 0, 0))
    )

    before = incident_repository.list_active_incidents()

    http_response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T17:00:00"}
    )
    cli_result = cli_runner.invoke(
        summary_cli_app, ["summary", "--reference-time", "2026-11-23T17:00:00"]
    )

    after = incident_repository.list_active_incidents()

    assert http_response.status_code == 200
    assert cli_result.exit_code == 0
    assert [incident.incident_id for incident in before] == [
        incident.incident_id for incident in after
    ]
    assert http_response.json() == json.loads(cli_result.stdout)


def test_bdd_resumen_responde_en_menos_de_dos_segundos_con_cien_incidentes(
    summary_api_client, incident_repository
):
    """
    Given hasta ~100 incidentes activos simultáneos (SC-006),
    When se consulta el resumen completo por HTTP,
    Then responde en menos de 2 segundos, sin paginar.
    """
    components = ["payments-gateway", "auth-identity", "database-cluster", "reporting-api"]
    severities = ["P0", "P1", "P2", "P3"]
    for idx in range(100):
        incident_repository.save_incident(
            _incident(
                f"INC-{idx:03d}",
                components[idx % len(components)],
                severities[idx % len(severities)],
                "OPEN" if idx % 2 == 0 else "IN_PROGRESS",
                datetime(2026, 11, 23, 8, 0, 0),
            )
        )

    start = time.perf_counter()
    response = summary_api_client.get(
        SUMMARY_ENDPOINT, params={"reference_time": "2026-11-23T17:00:00"}
    )
    elapsed_seconds = time.perf_counter() - start

    assert response.status_code == 200
    assert response.json()["total_active"] == 100
    assert elapsed_seconds < 2.0
