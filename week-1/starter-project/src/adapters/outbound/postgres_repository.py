"""Adaptador de salida PostgreSQL: implementa `IncidentRepositoryPort` (H004, ADR-004).

Replica el esquema de `sqlite_repository.py` (mismas columnas, mismo índice compuesto
`(component, status)` de ADR-001) usando SQL nativo sin ORM, vía `psycopg`. Los
timestamps se almacenan como texto ISO 8601 (`TEXT`), no como tipos nativos de fecha-hora
de PostgreSQL, para garantizar paridad exacta de comparación con SQLite (ADR-004,
Decisión 3). Al igual que el adaptador SQLite, no evalúa SLA: solo persiste y devuelve
entidades `Incident`.
"""

from datetime import datetime
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from src.domain.models import Incident, SeverityLevel
from src.domain.sla_calculator import SLA_POLICY_TABLE

# Estados considerados activos (constante interna fija; ver ADR-001).
_ACTIVE_STATUSES = ("OPEN", "IN_PROGRESS")


class PostgresIncidentRepository:
    """Implementa `IncidentRepositoryPort` sobre PostgreSQL vía `psycopg`."""

    def __init__(self, dsn: str) -> None:
        self.conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sla_policies (
                    severity TEXT PRIMARY KEY,
                    max_resolution_minutes INTEGER NOT NULL,
                    operates_24x7 BOOLEAN NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    component TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    symptom_category TEXT
                )
                """
            )
            for rule in SLA_POLICY_TABLE.values():
                cursor.execute(
                    """
                    INSERT INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (severity) DO UPDATE SET
                        max_resolution_minutes = EXCLUDED.max_resolution_minutes,
                        operates_24x7 = EXCLUDED.operates_24x7
                    """,
                    (rule.severity, rule.max_resolution_minutes, rule.operates_24x7),
                )
            # ADR-001: índice compuesto para el patrón de acceso component + status.
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incidents_component_status
                ON incidents (component, status)
                """
            )

    def save_incident(self, incident: Incident) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO incidents
                (incident_id, title, component, severity, status, created_at, resolved_at, symptom_category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    component = EXCLUDED.component,
                    severity = EXCLUDED.severity,
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    resolved_at = EXCLUDED.resolved_at,
                    symptom_category = EXCLUDED.symptom_category
                """,
                (
                    incident.incident_id,
                    incident.title,
                    incident.component,
                    incident.severity,
                    incident.status,
                    incident.created_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                    incident.symptom_category,
                ),
            )

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM incidents WHERE incident_id = %s",
                (incident_id,),
            )
            row = cursor.fetchone()
        return self._row_to_incident(row) if row else None

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        placeholders = ", ".join("%s" for _ in _ACTIVE_STATUSES)
        query = (
            "SELECT * FROM incidents "
            f"WHERE component = %s AND symptom_category = %s AND status IN ({placeholders}) "
            "ORDER BY incident_id"
        )
        with self.conn.cursor() as cursor:
            cursor.execute(query, (component, symptom_category, *_ACTIVE_STATUSES))
            rows = cursor.fetchall()
        return [self._row_to_incident(row) for row in rows]

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        placeholders = ", ".join("%s" for _ in _ACTIVE_STATUSES)
        if component_filter is not None:
            query = (
                "SELECT * FROM incidents "
                f"WHERE component = %s AND status IN ({placeholders}) "
                "ORDER BY incident_id"
            )
            params: tuple = (component_filter, *_ACTIVE_STATUSES)
        else:
            query = (
                "SELECT * FROM incidents "
                f"WHERE status IN ({placeholders}) "
                "ORDER BY incident_id"
            )
            params = _ACTIVE_STATUSES
        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [self._row_to_incident(row) for row in rows]

    def check_health(self) -> bool:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except psycopg.Error:
            return False

    @staticmethod
    def _row_to_incident(row: dict) -> Incident:
        severity: SeverityLevel = row["severity"]
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            component=row["component"],
            severity=severity,
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None
            ),
            symptom_category=row["symptom_category"],
        )
