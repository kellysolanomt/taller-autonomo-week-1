"""Adaptador de salida SQLite: implementa `IncidentRepositoryPort` (H002).

Reutiliza el esquema optimizado de ADR-001 (consulta única filtrada por `component` y
`status`, índice compuesto `(component, status)`), con una columna adicional nullable
`symptom_category` como preparación para H003. A diferencia del repositorio heredado de
Semana 1 (`src/incident_repository.py`), este adaptador no evalúa SLA: solo persiste y
devuelve entidades `Incident`; la evaluación de SLA vive en `IncidentService`
(`src/application/services.py`), nunca aquí.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from src.domain.models import Incident, SeverityLevel
from src.domain.sla_calculator import SLA_POLICY_TABLE

# Estados considerados activos (constante interna fija; ver ADR-001).
_ACTIVE_STATUSES = ("OPEN", "IN_PROGRESS")


class SQLiteIncidentRepository:
    """Implementa `IncidentRepositoryPort` sobre `sqlite3` de la biblioteca estándar."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sla_policies (
                severity TEXT PRIMARY KEY,
                max_resolution_minutes INTEGER NOT NULL,
                operates_24x7 INTEGER NOT NULL
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
                INSERT OR REPLACE INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                VALUES (?, ?, ?)
                """,
                (rule.severity, rule.max_resolution_minutes, 1 if rule.operates_24x7 else 0),
            )
        # ADR-001: índice compuesto para el patrón de acceso component + status.
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_incidents_component_status
            ON incidents (component, status)
            """
        )
        self.conn.commit()

    def save_incident(self, incident: Incident) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO incidents
            (incident_id, title, component, severity, status, created_at, resolved_at, symptom_category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        self.conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        cursor = self.conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,),
        )
        row = cursor.fetchone()
        return self._row_to_incident(row) if row else None

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        placeholders = ", ".join("?" for _ in _ACTIVE_STATUSES)
        query = (
            "SELECT * FROM incidents "
            f"WHERE component = ? AND symptom_category = ? AND status IN ({placeholders}) "
            "ORDER BY incident_id"
        )
        cursor = self.conn.execute(query, (component, symptom_category, *_ACTIVE_STATUSES))
        return [self._row_to_incident(row) for row in cursor]

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        placeholders = ", ".join("?" for _ in _ACTIVE_STATUSES)
        if component_filter is not None:
            query = (
                "SELECT * FROM incidents "
                f"WHERE component = ? AND status IN ({placeholders}) "
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
        cursor = self.conn.execute(query, params)
        return [self._row_to_incident(row) for row in cursor]

    def check_health(self) -> bool:
        try:
            self.conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> Incident:
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
