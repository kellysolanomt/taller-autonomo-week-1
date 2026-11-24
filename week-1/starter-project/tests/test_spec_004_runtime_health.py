"""Pruebas de aceptación BDD del Hito H004 (persistencia relacional dedicada y runtime
en contenedores).

Escenarios tomados de `specs/004-postgres-container-runtime/spec.md`. Las pruebas de
`/health` (Historia 1) y de conformidad de puerto/fábrica (Historia 2) son deterministas
y no requieren Docker ni un servidor PostgreSQL en ejecución (research.md, Decisión 4);
las pruebas de la Historia 3 (contenedores) verifican estáticamente el contenido de
`Dockerfile`, `.dockerignore` y `docker-compose.yml`.
"""

import json
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import create_cli_app
from src.adapters.outbound import factory as factory_module
from src.adapters.outbound.factory import create_repository, get_incident_repository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _UnhealthyRepository:
    """Doble de prueba: implementa `IncidentRepositoryPort` con `check_health() -> False`.

    Los demás métodos no se ejercitan en las pruebas de `/health` (spec.md → Historia 1).
    """

    def save_incident(self, incident: Incident) -> None:
        raise NotImplementedError

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        raise NotImplementedError

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        raise NotImplementedError

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        raise NotImplementedError

    def check_health(self) -> bool:
        return False


class _FlakyRepository:
    """Doble de prueba con estado mutable: `check_health()` devuelve `True` y luego `False`.

    Prueba que `/health` nunca cachea un resultado (RNF-003; spec.md → Casos Límite).
    """

    def __init__(self, results: list) -> None:
        self._results = list(results)

    def save_incident(self, incident: Incident) -> None:
        raise NotImplementedError

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        raise NotImplementedError

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        raise NotImplementedError

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        raise NotImplementedError

    def check_health(self) -> bool:
        return self._results.pop(0)


# --- Historia de Usuario 1: chequeo de salud por HTTP y CLI (P1) --------------------


def test_bdd_health_http_200_conectado():
    """
    Given el motor de persistencia configurado está disponible,
    When se consulta GET /health,
    Then la respuesta es 200 OK con {"status": "ok", "database": "connected"}.
    """
    client = TestClient(create_app(service=IncidentService(SQLiteIncidentRepository(":memory:"))))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_bdd_health_http_503_doble_de_prueba():
    """
    Given el adaptador de persistencia reporta que la conexión falló,
    When se consulta GET /health,
    Then la respuesta es 503 Service Unavailable con {"status": "error", "database": "unavailable"}.
    """
    client = TestClient(create_app(service=IncidentService(_UnhealthyRepository())))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_bdd_health_cli_exit0_conectado():
    """
    Given el motor de persistencia configurado está disponible,
    When se ejecuta el comando CLI health,
    Then el proceso termina con código de salida 0 e imprime el mismo cuerpo que la respuesta HTTP.
    """
    runner = CliRunner()
    app = create_cli_app(IncidentService(SQLiteIncidentRepository(":memory:")))

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "database": "connected"}


def test_bdd_health_cli_exit1_no_disponible():
    """
    Given el adaptador de persistencia reporta que la conexión falló,
    When se ejecuta el comando CLI health,
    Then el proceso termina con código de salida 1 e imprime el mismo cuerpo que la respuesta HTTP.
    """
    runner = CliRunner()
    app = create_cli_app(IncidentService(_UnhealthyRepository()))

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"status": "error", "database": "unavailable"}


def test_bdd_health_http_idempotente_repetible():
    """
    Given una consulta repetida de GET /health sin cambios en la disponibilidad,
    When se invoca varias veces seguidas,
    Then el resultado es el mismo en cada invocación.
    """
    client = TestClient(create_app(service=IncidentService(SQLiteIncidentRepository(":memory:"))))

    first = client.get("/health")
    second = client.get("/health")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"status": "ok", "database": "connected"}


def test_bdd_health_http_refleja_cambio_de_estado_sin_cache():
    """
    Given un repositorio cuyo check_health() cambia de True a False entre llamadas,
    When se consulta GET /health dos veces seguidas sobre el mismo cliente,
    Then la primera respuesta es 200/connected y la segunda es 503/unavailable
         (RNF-003: el resultado nunca se cachea).
    """
    service = IncidentService(_FlakyRepository([True, False]))
    client = TestClient(create_app(service=service))

    first = client.get("/health")
    second = client.get("/health")

    assert first.status_code == 200
    assert first.json() == {"status": "ok", "database": "connected"}
    assert second.status_code == 503
    assert second.json() == {"status": "error", "database": "unavailable"}


# --- Historia de Usuario 2: selección transparente de motor por DATABASE_URL (P2) ---


class _DummyPostgresDouble:
    """Doble mínimo de `PostgresIncidentRepository`: cumple el puerto sin red."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def save_incident(self, incident: Incident) -> None:
        raise NotImplementedError

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        raise NotImplementedError

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        raise NotImplementedError

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        raise NotImplementedError

    def check_health(self) -> bool:
        return True


def test_sqlite_repository_cumple_incident_repository_port():
    """SQLiteIncidentRepository cumple IncidentRepositoryPort (Protocol runtime_checkable)."""
    assert isinstance(SQLiteIncidentRepository(":memory:"), IncidentRepositoryPort)


def test_postgres_repository_cumple_incident_repository_port_estructural():
    """
    PostgresIncidentRepository cumple IncidentRepositoryPort de forma estructural
    (issubclass sobre un Protocol de solo métodos), sin instanciar la clase ni abrir
    ninguna conexión real (research.md, Decisión 4).
    """
    assert issubclass(PostgresIncidentRepository, IncidentRepositoryPort)


def test_create_repository_esquema_sqlite():
    """
    Given DATABASE_URL tiene el esquema sqlite:///,
    When el servicio construye su repositorio,
    Then queda respaldado por el adaptador de SQLite.
    """
    repository = create_repository("sqlite:///:memory:")

    assert isinstance(repository, SQLiteIncidentRepository)


def test_get_incident_repository_sin_database_url_usa_sqlite_memoria(monkeypatch):
    """
    Given DATABASE_URL no está definida,
    When el servicio construye su repositorio,
    Then queda respaldado por el adaptador de SQLite en memoria.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)

    repository = get_incident_repository()

    assert isinstance(repository, SQLiteIncidentRepository)


def test_create_repository_esquema_postgresql_selecciona_adaptador(monkeypatch):
    """
    Given DATABASE_URL tiene el esquema postgresql://...,
    When el servicio construye su repositorio,
    Then queda respaldado por el adaptador de PostgreSQL (verificado con un doble sin red).
    """
    monkeypatch.setattr(factory_module, "PostgresIncidentRepository", _DummyPostgresDouble)

    repository = create_repository("postgresql://user:pass@host:5432/db")

    assert isinstance(repository, _DummyPostgresDouble)
    assert repository.dsn == "postgresql://user:pass@host:5432/db"


def test_create_repository_esquema_no_soportado_lanza_valueerror():
    """
    Given un valor de DATABASE_URL con un esquema distinto de sqlite:/// o postgresql://,
    When el servicio intenta construir su repositorio,
    Then la construcción se rechaza con ValueError identificando el esquema.
    """
    with pytest.raises(ValueError, match="mysql://"):
        create_repository("mysql://host/db")


# --- Historia de Usuario 3: orquestación reproducible en contenedores (P3) ----------


def test_dockerfile_usa_python312_slim_y_uv():
    """
    Given el código fuente del servicio api,
    When se construye su imagen de contenedor,
    Then el Dockerfile usa python:3.12-slim e invoca uv.
    """
    contents = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in contents
    assert "uv sync" in contents or "uv run" in contents


def test_dockerignore_excluye_entornos_virtuales_y_artefactos_de_prueba():
    """.dockerignore excluye entornos virtuales, caches, historial de VCS y pruebas (RNF-004)."""
    contents = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    for expected in (".venv", "__pycache__", ".git", "tests"):
        assert expected in contents


def test_docker_compose_declara_api_y_db_con_healthchecks_y_depends_on():
    """
    Given una máquina con Docker y Docker Compose instalados,
    When se levanta el stack definido en docker-compose.yml,
    Then se declaran los servicios api y db con sus healthchecks y la dependencia
         de arranque de api sobre db saludable.
    """
    contents = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "db:" in contents
    assert "api:" in contents
    assert "postgres:16-alpine" in contents
    assert "pg_isready" in contents
    assert "pgdata" in contents  # volumen con nombre
    assert "condition: service_healthy" in contents
    assert "DATABASE_URL" in contents and "db:5432" in contents
    assert "/health" in contents
