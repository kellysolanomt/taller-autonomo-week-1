"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps).

NOTA PEDAGÓGICA (Semana 1 — Enfoque 100% AI for Software Engineering):
Este módulo implementa las reglas de negocio para clasificar reportes entrantes y
asignarlos a un equipo de ingeniería (`Backend-Core`, `Platform-SRE`, `Data-DBA`,
`Security-IAM`).

Actualmente presenta deuda técnica que los estudiantes diagnosticarán y refactorizarán
asistidos por IA (usando Context Engineering, Few-Shot, Chain-of-Thought y Self-Consistency):
1. Clasificación frágil con cadenas `if/elif` acopladas y sensibles a palabras aisladas
   (p. ej., cualquier mensaje con la palabra "hoy" se clasifica erróneamente como `P0`).
2. No asigna el equipo responsable (`recommended_team`) ni genera una clave de
   correlación (`duplicate_group_key`) para detectar incidentes repetidos del mismo
   componente.
"""

import json
from pathlib import Path
from typing import Dict, List

from src.models import SeverityLevel, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente aplicando reglas heurísticas iniciales.

    DEUDA TÉCNICA INTENCIONAL:
    - Evalúa palabras sueltas ("hoy", "urgente") antes de analizar el impacto real
      (caída global vs. cuenta individual vs. entorno de staging).
    - No normaliza componentes ni identifica el equipo de guardia correspondiente.
    """
    text_lower = raw_text.lower()

    # Bug de diseño: si un usuario dice "necesito acceder hoy" por su cuenta bloqueada,
    # se dispara como P0 antes de verificar si es una caída global o un caso individual.
    if "urgente" in text_lower or "hoy" in text_lower or "502" in text_lower:
        severity: SeverityLevel = "P0"
    elif "94%" in text_lower or "timeout" in text_lower:
        severity = "P1"
    elif "lenta" in text_lower or "segundos" in text_lower:
        severity = "P2"
    else:
        severity = "P3"

    if "pago" in text_lower or "cobro" in text_lower or "tarjeta" in text_lower:
        component = "payments-gateway"
    elif "cuenta" in text_lower or "ingresar" in text_lower:
        component = "auth-identity"
    elif "postgresql" in text_lower or "conexiones" in text_lower:
        component = "database-cluster"
    elif "certificado" in text_lower or "tls" in text_lower:
        component = "infra-certificates"
    elif "botón" in text_lower or "color" in text_lower:
        component = "frontend-ui"
    else:
        component = "reporting-api"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=f"Clasificación heurística legacy asignada a {component} ({severity}).",
    )


def _run_triage_audit() -> None:
    """Ejecuta el motor actual sobre los 10 incidentes de prueba para evidenciar fallos."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))

    print("=== Auditoría del Motor de Triaje Actual (`src/triage_rules.py`) ===")
    print(f"{'ID':<10} | {'Sev.':<5} | {'Componente':<20} | {'Extracto del Reporte'}")
    print("-" * 88)
    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        snippet = item["raw_text"][:45] + "..." if len(item["raw_text"]) > 45 else item["raw_text"]
        print(f"{result.incident_id:<10} | {result.severity:<5} | {result.component:<20} | {snippet}")
    print("-" * 88)
    print(
        "Observa los problemas en la salida actual:\n"
        "  - INC-1002 (cuenta individual bloqueada) y INC-1009 (exportación Excel lenta)\n"
        "    se clasifican como P0 solo porque el usuario escribió la palabra 'hoy'.\n"
        "  - INC-1007 (fuga crítica de facturas entre empresas por company_id en URL)\n"
        "    se clasifica como P3 porque no contiene las palabras 'urgente' ni '502'."
    )


if __name__ == "__main__":
    _run_triage_audit()

