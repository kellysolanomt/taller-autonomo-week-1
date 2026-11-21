"""Fixtures compartidas para las pruebas de aceptación BDD del Hito H001."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app

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
