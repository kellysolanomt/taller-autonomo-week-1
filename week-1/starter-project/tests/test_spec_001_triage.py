"""Pruebas de aceptación BDD del Hito H001 (triaje multi-interfaz).

Escenarios tomados de `specs/001-triage-endpoint-manual.md` §8, ejecutados contra
los adaptadores reales (API vía `TestClient`, CLI vía `CliRunner`), ambos
delegando en el mismo `IncidentService`.
"""

import json

from tests.conftest import ACCOUNT_BLOCKED_TODAY_RAW_TEXT, PAYMENTS_OUTAGE_RAW_TEXT

TRIAGE_ENDPOINT = "/api/v1/incidents/triage"


def test_caida_critica_http_502_en_pasarela_de_pagos(api_client):
    """
    Given un reporte de caída HTTP 502 en la pasarela de pagos con alcance global,
    When se envía al endpoint de triaje,
    Then la respuesta es 200 OK con severidad P0, equipo Backend-Core y la clave
         de duplicado "payments-gateway:outage".
    """
    response = api_client.post(
        TRIAGE_ENDPOINT,
        json={"incident_id": "INC-1001", "raw_text": PAYMENTS_OUTAGE_RAW_TEXT},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == "payments-gateway:outage"


def test_cuenta_individual_bloqueada_mencionando_hoy(api_client):
    """
    Given un reporte de cuenta individual bloqueada que menciona "hoy",
    When se envía al endpoint de triaje,
    Then la respuesta es 200 OK con severidad P2 (nunca P0: la palabra "hoy" no
         eleva la severidad) y equipo Security-IAM.
    """
    response = api_client.post(
        TRIAGE_ENDPOINT,
        json={"incident_id": "INC-1002", "raw_text": ACCOUNT_BLOCKED_TODAY_RAW_TEXT},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["severity"] == "P2"
    assert body["severity"] != "P0"
    assert body["recommended_team"] == "Security-IAM"


def test_entradas_vacias_o_con_solo_espacios(api_client):
    """
    Given un `raw_text` compuesto solo de espacios,
    When se envía al endpoint de triaje,
    Then la respuesta es un error de validación (422) con una clave "error".
    """
    response = api_client.post(
        TRIAGE_ENDPOINT,
        json={"incident_id": "INC-1003", "raw_text": "   "},
    )

    assert response.status_code == 422
    assert "error" in response.json()


def test_paridad_en_cli(cli_runner, cli_app_under_test):
    """
    Given el mismo reporte de caída crítica de la pasarela de pagos,
    When se invoca vía la CLI (`triage --incident-id ... --raw-text ...`),
    Then la salida estándar es JSON válido con severidad P0 y el proceso termina
         con código de salida 0.
    """
    result = cli_runner.invoke(
        cli_app_under_test,
        ["triage", "--incident-id", "INC-1001", "--raw-text", PAYMENTS_OUTAGE_RAW_TEXT],
    )

    assert result.exit_code == 0
    body = json.loads(result.stdout)
    assert body["severity"] == "P0"
    assert body["recommended_team"] == "Backend-Core"
