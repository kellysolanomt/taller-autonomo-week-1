"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

NOTA PEDAGÓGICA (Semana 1):
Este módulo contiene una simplificación/deuda técnica intencional que será analizada
durante la Fase 1 (auditoría de contexto con LSP) y corregida en la Actividad Autónoma:
- Actualmente calcula `elapsed_minutes` usando tiempo calendario continuo (24/7) para
  TODOS los niveles de severidad, ignorando la propiedad `operates_24x7=False` de los
  incidentes P2 y P3 (que solo deberían descontar tiempo en horario hábil: Lunes a Viernes,
  08:00 a 18:00).
"""

from datetime import datetime
from typing import Dict

from src.models import Incident, SLAEvaluation, SLARule, SeverityLevel

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    # TODO(week-1-taller): Cuando rule.operates_24x7 es False (P2 y P3), solo deben
    # contabilizarse los minutos dentro del horario hábil (Lunes-Viernes 08:00-18:00).
    delta_seconds = (end_time - incident.created_at).total_seconds()
    elapsed_minutes = int(delta_seconds // 60)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED"
        and not is_breached
        and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


def _run_demo() -> None:
    """Ejecuta una demostración rápida del cálculo determinista de SLA."""
    print("=== Demostración de Cálculo Determinista de SLA ===")
    sample_incident = Incident(
        incident_id="INC-2001",
        title="Latencia elevada en reporte de órdenes",
        component="reporting-api",
        severity="P2",
        status="OPEN",
        created_at=datetime(2026, 11, 6, 17, 0, 0),  # Viernes 17:00
    )
    # Lunes siguiente a las 09:00 (solo 2 horas hábiles reales, pero 64 horas calendario)
    monday_morning = datetime(2026, 11, 9, 9, 0, 0)
    evaluation = evaluate_sla_status(sample_incident, reference_time=monday_morning)

    print(f"Incidente: {evaluation.incident_id} (Severidad {evaluation.severity})")
    print(f"Minutos transcurridos calculados: {evaluation.elapsed_minutes} min")
    print(f"Minutos permitidos por SLA:       {evaluation.allowed_minutes} min")
    print(f"¿SLA Incumplido?:                 {evaluation.is_breached}")
    print(
        "Nota: Observa que para un ticket P2 creado el viernes a las 17:00 y evaluado "
        "el lunes a las 09:00 se contaron todo el sábado y domingo como tiempo activo."
    )


if __name__ == "__main__":
    _run_demo()

