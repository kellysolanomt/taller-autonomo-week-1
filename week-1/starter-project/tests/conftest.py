"""Fixtures compartidas para las pruebas de aceptación BDD de H001 y H002."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app, create_cli_app
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.services import IncidentService

PAYMENTS_OUTAGE_RAW_TEXT = (
    "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway para todos los "
    "comercios desde hace 10 minutos."
)
ACCOUNT_BLOCKED_TODAY_RAW_TEXT = (
    "Necesito acceder hoy a mi cuenta, quedó bloqueada tras varios intentos de ingreso."
)


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_app_under_test():
    return cli_app


@pytest.fixture
def incident_repository() -> SQLiteIncidentRepository:
    """Repositorio SQLite en memoria, nuevo y aislado por prueba (skill `bdd-acceptance`)."""
    return SQLiteIncidentRepository(":memory:")


@pytest.fixture
def incident_service(incident_repository: SQLiteIncidentRepository) -> IncidentService:
    return IncidentService(incident_repository)


@pytest.fixture
def summary_api_client(incident_service: IncidentService) -> TestClient:
    """Cliente HTTP que comparte `incident_service`/`incident_repository` con la prueba."""
    return TestClient(create_app(service=incident_service))


@pytest.fixture
def summary_cli_app(incident_service: IncidentService):
    """App CLI que comparte `incident_service`/`incident_repository` con la prueba."""
    return create_cli_app(incident_service)
