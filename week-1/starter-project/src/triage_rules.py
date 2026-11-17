"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps).

Flujo (de impacto a detalle, nunca por palabras sueltas de urgencia):
    1. Síntoma  -> qué está pasando (fuga de datos, caída, capacidad, ...).
    2. Alcance  -> a quién afecta (global, individual, staging).
    3. Componente, severidad y equipo se derivan de (síntoma, alcance).
    4. `duplicate_group_key` = "<component>:<symptom_category>".

Palabras como "hoy" o "urgente" NO influyen en la severidad: expresan prisa de
quien reporta, no impacto en la plataforma.
"""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from src.models import (
    ImpactScope,
    SeverityLevel,
    SymptomCategory,
    TeamName,
    TriageResult,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"

# --- Tablas de reglas -------------------------------------------------------

# Severidad base por síntoma (se ajusta luego según el alcance).
_SEVERITY_BY_SYMPTOM: Dict[SymptomCategory, SeverityLevel] = {
    "data_exposure": "P0",
    "outage": "P0",
    "capacity": "P1",
    "access_blocked": "P2",
    "latency": "P2",
    "cert_expiry": "P3",
    "ui_cosmetic": "P3",
    "other": "P3",
}

# Componente forzado por síntoma (independiente de qué módulo mencione el texto:
# una fuga vía la pasarela de pagos sigue siendo un fallo de aislamiento/identidad).
_COMPONENT_BY_SYMPTOM: Dict[SymptomCategory, str] = {
    "data_exposure": "auth-identity",
    "access_blocked": "auth-identity",
    "cert_expiry": "infra-certificates",
    "ui_cosmetic": "frontend-ui",
}

# Componente por palabras clave (el orden importa; los textos van sin tildes).
_COMPONENT_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("database-cluster", ("postgresql", "postgres", "conexiones", "base de datos")),
    ("payments-gateway", ("pago", "cobro", "tarjeta", "pasarela")),
    ("auth-identity", ("cuenta", "ingresar", "login", "contrasena")),
    ("infra-certificates", ("certificado", "tls", "ssl")),
    ("frontend-ui", ("boton", "color")),
]
_DEFAULT_COMPONENT = "reporting-api"

# Equipo recomendado: primero por síntoma, luego por componente.
_TEAM_BY_SYMPTOM: Dict[SymptomCategory, TeamName] = {
    "data_exposure": "Security-IAM",
    "access_blocked": "Security-IAM",
    "cert_expiry": "Platform-SRE",
}
_TEAM_BY_COMPONENT: Dict[str, TeamName] = {
    "auth-identity": "Security-IAM",
    "database-cluster": "Data-DBA",
    "infra-certificates": "Platform-SRE",
    "payments-gateway": "Backend-Core",
    "reporting-api": "Backend-Core",
    "frontend-ui": "Backend-Core",
}

_SEVERITY_ORDER: Dict[SeverityLevel, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# --- Patrones de síntoma / alcance -----------------------------------------

_RE_DATA_EXPOSURE = re.compile(
    r"company_id|otras empresas|otros comercios|otros clientes|otro tenant|"
    r"fuga|expos|filtrad|datos de terceros"
)
_RE_OUTAGE = re.compile(
    r"\b50[234]\b|caid[ao]|fuera de servicio|no responde|no funciona|"
    r"no (?:se )?puede(?:n)? (?:cobrar|pagar|procesar)|no procesa"
)
_RE_CAPACITY = re.compile(
    r"(?:\b(?:8\d|9\d|100)\s?%)|saturaci|sobrecarga|pool de conexiones|conexiones (?:activas|agotadas)"
)
_RE_ACCESS = re.compile(
    r"bloquead|no puedo (?:ingresar|acceder|entrar)|intentos|restablecer|"
    r"contrasena|necesito (?:acceder|ingresar)"
)
_RE_CERT = re.compile(r"certificado|\btls\b|\bssl\b")
_RE_CERT_BROKEN = re.compile(r"ya (?:vencio|expiro)|esta (?:vencido|expirado)|invalido|no es valido")
_RE_LATENCY = re.compile(r"lent[ao]|segundos|\d+\s?s\b|tard|demora|latencia|timeout")
_RE_UI = re.compile(r"boton|color|alineaci|tipograf|logo|texto")

_RE_INDIVIDUAL = re.compile(
    r"\bmi (?:cuenta|usuario)\b|\bmi usuario\b|un (?:solo )?usuario|solo (?:a )?mi\b|"
    r"mi exportaci|mi reporte|descarga del reporte"
)
_RE_STAGING = re.compile(r"staging|entorno de (?:pruebas|prueba|qa)|\bqa\b|sandbox")
_DB_HINT = ("postgresql", "postgres", "conexiones", "base de datos")


def _normalize(text: str) -> str:
    """Minúsculas y sin tildes, para que 'botón' y 'boton' coincidan."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _detect_symptom(text: str) -> SymptomCategory:
    """Elige el síntoma más grave presente (el orden es el orden de gravedad)."""
    if _RE_DATA_EXPOSURE.search(text):
        return "data_exposure"
    if _RE_OUTAGE.search(text):
        return "outage"
    if _RE_CERT.search(text):
        return "outage" if _RE_CERT_BROKEN.search(text) else "cert_expiry"
    if _RE_CAPACITY.search(text):
        return "capacity"
    # `timeout` junto a términos de base de datos es una alerta de capacidad.
    if "timeout" in text and any(h in text for h in _DB_HINT):
        return "capacity"
    if _RE_ACCESS.search(text):
        return "access_blocked"
    if _RE_LATENCY.search(text):
        return "latency"
    if _RE_UI.search(text):
        return "ui_cosmetic"
    return "other"


def _detect_scope(text: str) -> ImpactScope:
    if _RE_STAGING.search(text):
        return "staging"
    if _RE_INDIVIDUAL.search(text):
        return "individual"
    return "global"


def _detect_component(text: str, symptom: SymptomCategory) -> str:
    if symptom in _COMPONENT_BY_SYMPTOM:
        return _COMPONENT_BY_SYMPTOM[symptom]
    for component, keywords in _COMPONENT_KEYWORDS:
        if any(k in text for k in keywords):
            return component
    return _DEFAULT_COMPONENT


def _adjust_severity(
    base: SeverityLevel, symptom: SymptomCategory, scope: ImpactScope
) -> SeverityLevel:
    """Ajusta la severidad base por alcance.

    - Una caída que afecta a un solo usuario o a staging no es P0: se limita a P2.
    - La exposición de datos se mantiene P0 siempre (criterio conservador de privacidad).
    """
    if symptom == "data_exposure":
        return base
    if scope in ("individual", "staging") and _SEVERITY_ORDER[base] < _SEVERITY_ORDER["P2"]:
        return "P2"
    return base


def _recommend_team(component: str, symptom: SymptomCategory) -> TeamName:
    return _TEAM_BY_SYMPTOM.get(symptom) or _TEAM_BY_COMPONENT.get(component, "Backend-Core")


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte: severidad, componente, equipo y clave de duplicado."""
    text = _normalize(raw_text)

    symptom = _detect_symptom(text)
    scope = _detect_scope(text)
    component = _detect_component(text, symptom)
    severity = _adjust_severity(_SEVERITY_BY_SYMPTOM[symptom], symptom, scope)
    team = _recommend_team(component, symptom)

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=(
            f"Síntoma '{symptom}' con alcance '{scope}' en {component} -> {severity}; "
            f"se enruta a {team}."
        ),
        recommended_team=team,
        duplicate_group_key=f"{component}:{symptom}",
        symptom_category=symptom,
        impact_scope=scope,
    )


def group_duplicates(results: List[TriageResult]) -> Dict[str, List[str]]:
    """Agrupa IDs por `duplicate_group_key`; solo devuelve grupos con 2+ incidentes."""
    groups: Dict[str, List[str]] = defaultdict(list)
    for r in results:
        groups[r.duplicate_group_key].append(r.incident_id)
    return {k: v for k, v in groups.items() if len(v) > 1}


def _run_triage_audit() -> None:
    """Ejecuta el motor sobre los incidentes de prueba y muestra los duplicados."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    results = [classify_incident_report(i["id"], i["raw_text"]) for i in incidents]

    print("=== Auditoría del Motor de Triaje (`src/triage_rules.py`) ===")
    print(f"{'ID':<9} | {'Sev':<3} | {'Equipo':<13} | {'Clave de duplicado':<36} | Extracto")
    print("-" * 110)
    for item, r in zip(incidents, results):
        raw = item["raw_text"]
        snippet = raw[:40] + "..." if len(raw) > 40 else raw
        print(
            f"{r.incident_id:<9} | {r.severity:<3} | {r.recommended_team:<13} | "
            f"{r.duplicate_group_key:<36} | {snippet}"
        )
    print("-" * 110)
    for key, ids in group_duplicates(results).items():
        print(f"Duplicados [{key}]: {', '.join(ids)}")


if __name__ == "__main__":
    _run_triage_audit()