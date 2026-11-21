"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA).

Según ADR-002, los incidentes P0 y P1 (`operates_24x7=True`) miden minutos de pared,
mientras que P2 y P3 (`operates_24x7=False`) solo descuentan minutos dentro del horario
hábil: Lunes a Viernes, 08:00 a 18:00 (600 minutos por día). Sábados y domingos no
consumen SLA. Los datetimes son naive, en hora local de operación.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from src.domain.models import Incident, SLAEvaluation, SLARule, SeverityLevel

# Horario hábil (ADR-002): lunes a viernes, 08:00-18:00.
BUSINESS_DAY_START_HOUR = 8
BUSINESS_DAY_END_HOUR = 18
LAST_BUSINESS_WEEKDAY = 4  # datetime.weekday(): 0=lunes ... 4=viernes

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


def _require_naive(name: str, value: Optional[datetime]) -> None:
    """Rechaza datetimes con zona horaria: el calculador opera en hora local naive."""
    if value is not None and value.utcoffset() is not None:
        raise ValueError(
            f"{name} no debe incluir zona horaria (tzinfo); "
            "se esperan datetimes naive en hora local de operación."
        )


def business_seconds_between(start: datetime, end: datetime) -> float:
    """Segundos hábiles (lunes-viernes, 08:00-18:00) contenidos en ``[start, end]``.

    Función pura, O(D) en días calendario: recorre día a día y suma el solape del
    intervalo con la ventana hábil de cada día. Sábados y domingos aportan cero.
    """
    total_seconds = 0.0
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        if day.weekday() <= LAST_BUSINESS_WEEKDAY:
            window_open = day + timedelta(hours=BUSINESS_DAY_START_HOUR)
            window_close = day + timedelta(hours=BUSINESS_DAY_END_HOUR)
            overlap_start = max(start, window_open)
            overlap_end = min(end, window_close)
            if overlap_start < overlap_end:
                total_seconds += (overlap_end - overlap_start).total_seconds()
        day += timedelta(days=1)
    return total_seconds


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    P0 y P1 miden minutos de pared; P2 y P3 miden minutos hábiles. Un incidente no
    resuelto requiere escalamiento al alcanzar el umbral, esté o no ya vencido. Todo
    incidente `RESOLVED` debe traer `resolved_at`; esa invariante la garantiza quien
    cambia el estado, no este calculador. Los datetimes deben ser naive; si alguno
    incluye `tzinfo` se lanza `ValueError`.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
        Los minutos son hábiles para P2/P3 y de pared para P0/P1.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    _require_naive("created_at", incident.created_at)
    _require_naive("resolved_at", incident.resolved_at)
    _require_naive("reference_time", reference_time)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        elapsed_seconds = (end_time - incident.created_at).total_seconds()
    else:
        elapsed_seconds = business_seconds_between(incident.created_at, end_time)

    # Se suman segundos y se trunca a minutos una sola vez, al final.
    elapsed_minutes = int(elapsed_seconds // 60)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED" and elapsed_minutes >= escalation_limit
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
        "Nota: para un ticket P2 creado el viernes a las 17:00 y evaluado el lunes a "
        "las 09:00 solo se cuentan las horas hábiles (1 h del viernes y 1 h del lunes); "
        "sábado y domingo no consumen SLA."
    )


def _run_edge_cases() -> bool:
    """Verifica casos borde contra minutos calculados a mano. Retorna True si todos pasan.

    Calendario de referencia (2026): 6-nov viernes, 7-nov sábado, 8-nov domingo,
    9-nov lunes, 10-nov martes, 23-nov lunes.
    """
    d = datetime
    # (descripción, severidad, estado, creado, resuelto, referencia,
    #  elapsed esperado, is_breached esperado, requires_escalation esperado)
    cases = [
        ("P2 cruce de fin de semana (vie 17:00 -> lun 09:00)", "P2", "OPEN",
         d(2026, 11, 6, 17, 0), None, d(2026, 11, 9, 9, 0), 120, False, False),
        ("P2 creado en sábado (sáb 10:00 -> lun 08:30)", "P2", "OPEN",
         d(2026, 11, 7, 10, 0), None, d(2026, 11, 9, 8, 30), 30, False, False),
        ("P2 viernes 17:00 evaluado el domingo 20:00", "P2", "OPEN",
         d(2026, 11, 6, 17, 0), None, d(2026, 11, 8, 20, 0), 60, False, False),
        ("P3 solo fin de semana (sáb 09:00 -> dom 18:00)", "P3", "OPEN",
         d(2026, 11, 7, 9, 0), None, d(2026, 11, 8, 18, 0), 0, False, False),
        ("P2 creado antes de abrir (lun 06:30 -> 09:00)", "P2", "OPEN",
         d(2026, 11, 9, 6, 30), None, d(2026, 11, 9, 9, 0), 60, False, False),
        ("P2 creado después de cerrar (lun 19:30 -> mar 08:45)", "P2", "OPEN",
         d(2026, 11, 9, 19, 30), None, d(2026, 11, 10, 8, 45), 45, False, False),
        ("P2 día hábil completo (lun 08:00 -> 18:00)", "P2", "OPEN",
         d(2026, 11, 9, 8, 0), None, d(2026, 11, 9, 18, 0), 600, True, True),
        ("P1 24/7 mismo cruce (vie 17:00 -> lun 09:00)", "P1", "OPEN",
         d(2026, 11, 6, 17, 0), None, d(2026, 11, 9, 9, 0), 3840, True, True),
        ("P0 24/7 en viernes tarde (17:00 -> 17:50)", "P0", "OPEN",
         d(2026, 11, 6, 17, 0), None, d(2026, 11, 6, 17, 50), 50, False, True),
        ("P3 dos semanas (lun 08:00 -> lun +14 días)", "P3", "OPEN",
         d(2026, 11, 9, 8, 0), None, d(2026, 11, 23, 8, 0), 6000, True, True),
        ("P2 justo antes del umbral (359 min)", "P2", "OPEN",
         d(2026, 11, 9, 8, 0), None, d(2026, 11, 9, 13, 59), 359, False, False),
        ("P2 exacto en el umbral (360 min)", "P2", "OPEN",
         d(2026, 11, 9, 8, 0), None, d(2026, 11, 9, 14, 0), 360, False, True),
        ("P2 exacto en el límite SLA (480 min, no vencido)", "P2", "OPEN",
         d(2026, 11, 9, 8, 0), None, d(2026, 11, 9, 16, 0), 480, False, True),
        ("P2 RESOLVED detiene el reloj (vie 17:00 -> lun 08:30)", "P2", "RESOLVED",
         d(2026, 11, 6, 17, 0), d(2026, 11, 9, 8, 30), d(2026, 11, 20, 12, 0), 90, False, False),
        ("Truncado único (vie 17:59:30 -> lun 08:00:30)", "P2", "OPEN",
         d(2026, 11, 6, 17, 59, 30), None, d(2026, 11, 9, 8, 0, 30), 1, False, False),
    ]

    all_ok = True
    print("\n=== Casos borde: minutos esperados vs. calculados ===")
    for name, sev, status, created, resolved, ref, exp_min, exp_breach, exp_esc in cases:
        incident = Incident(
            incident_id="EDGE", title=name, component="edge", severity=sev,
            status=status, created_at=created, resolved_at=resolved,
        )
        ev = evaluate_sla_status(incident, reference_time=ref)
        ok = (ev.elapsed_minutes, ev.is_breached, ev.requires_escalation) == (
            exp_min, exp_breach, exp_esc,
        )
        all_ok &= ok
        print(
            f"[{'OK' if ok else 'FALLO'}] {name}: {ev.elapsed_minutes} min "
            f"(esperado {exp_min}), vencido={ev.is_breached} (esperado {exp_breach}), "
            f"escala={ev.requires_escalation} (esperado {exp_esc})"
        )

    # Casos que deben lanzar ValueError.
    base = Incident("EDGE", "t", "edge", "P2", "OPEN", d(2026, 11, 9, 9, 0))
    error_cases = [
        ("referencia anterior a la creación", base, d(2026, 11, 9, 8, 0)),
        ("reference_time con tzinfo", base, d(2026, 11, 9, 10, 0, tzinfo=timezone.utc)),
        (
            "created_at con tzinfo",
            Incident("EDGE", "t", "edge", "P2", "OPEN", d(2026, 11, 9, 9, 0, tzinfo=timezone.utc)),
            d(2026, 11, 9, 10, 0),
        ),
        ("severidad inválida", Incident("EDGE", "t", "edge", "P9", "OPEN", d(2026, 11, 9, 9, 0)),
         d(2026, 11, 9, 10, 0)),
    ]
    for name, incident, ref in error_cases:
        try:
            evaluate_sla_status(incident, reference_time=ref)
            ok = False
        except ValueError:
            ok = True
        all_ok &= ok
        print(f"[{'OK' if ok else 'FALLO'}] ValueError esperado: {name}")

    print("Resultado:", "todos los casos pasaron." if all_ok else "HAY CASOS FALLIDOS.")
    return all_ok


if __name__ == "__main__":
    _run_demo()
    if not _run_edge_cases():
        raise SystemExit(1)
