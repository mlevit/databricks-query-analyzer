"""Persistence layer for analysis history, annotations, and trending.

Provides a ``Storage`` protocol with a SQLite implementation for local dev and
a Delta table implementation for production on Databricks.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Protocol

from backend.models import (
    AnalysisRecord,
    AnalysisResult,
    AnnotationStatus,
    RecommendationAnnotation,
    TrendPoint,
)

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


class Storage(Protocol):
    def save_analysis(self, result: AnalysisResult, health_score: int) -> None: ...
    def get_history(self, statement_id: str) -> list[AnalysisRecord]: ...
    def get_all_history(self, *, limit: int = 100) -> list[AnalysisRecord]: ...
    def get_trend(self, statement_id: str) -> list[TrendPoint]: ...
    def get_global_trend(self, *, limit: int = 200) -> list[TrendPoint]: ...
    def save_annotation(self, annotation: RecommendationAnnotation) -> None: ...
    def get_annotations(self, statement_id: str) -> list[RecommendationAnnotation]: ...
    def delete_annotation(self, annotation_id: str) -> bool: ...


class SqliteStorage:
    """SQLite-backed storage for local development."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.environ.get(
            "DQA_STORAGE_PATH", os.path.join(os.path.dirname(__file__), ".dqa_history.db")
        )
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    statement_id TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    health_score INTEGER NOT NULL DEFAULT 100,
                    recommendation_count INTEGER NOT NULL DEFAULT 0,
                    critical_count INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    info_count INTEGER NOT NULL DEFAULT 0,
                    total_duration_ms INTEGER,
                    statement_text TEXT NOT NULL DEFAULT '',
                    result_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_history_stmt ON analysis_history(statement_id);
                CREATE INDEX IF NOT EXISTS idx_history_time ON analysis_history(analyzed_at);

                CREATE TABLE IF NOT EXISTS annotations (
                    id TEXT PRIMARY KEY,
                    statement_id TEXT NOT NULL,
                    recommendation_title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ann_stmt ON annotations(statement_id);
            """)

    def save_analysis(self, result: AnalysisResult, health_score: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        recs = result.recommendations
        critical = sum(1 for r in recs if r.severity.value == "critical")
        warning = sum(1 for r in recs if r.severity.value == "warning")
        info = sum(1 for r in recs if r.severity.value == "info")

        with self._conn() as conn:
            conn.execute(
                """INSERT INTO analysis_history
                   (statement_id, analyzed_at, health_score, recommendation_count,
                    critical_count, warning_count, info_count, total_duration_ms,
                    statement_text, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.query_metrics.statement_id,
                    now,
                    health_score,
                    len(recs),
                    critical,
                    warning,
                    info,
                    result.query_metrics.total_duration_ms,
                    result.query_metrics.statement_text[:500],
                    json.dumps(result.model_dump(mode="json")),
                ),
            )

    def get_history(self, statement_id: str) -> list[AnalysisRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_history WHERE statement_id = ? ORDER BY analyzed_at DESC",
                (statement_id,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_all_history(self, *, limit: int = 100) -> list[AnalysisRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_history ORDER BY analyzed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_trend(self, statement_id: str) -> list[TrendPoint]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT analyzed_at, health_score, recommendation_count "
                "FROM analysis_history WHERE statement_id = ? ORDER BY analyzed_at",
                (statement_id,),
            ).fetchall()
        return [TrendPoint(analyzed_at=r["analyzed_at"], health_score=r["health_score"],
                           recommendation_count=r["recommendation_count"]) for r in rows]

    def get_global_trend(self, *, limit: int = 200) -> list[TrendPoint]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT analyzed_at, health_score, recommendation_count "
                "FROM analysis_history ORDER BY analyzed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [TrendPoint(analyzed_at=r["analyzed_at"], health_score=r["health_score"],
                           recommendation_count=r["recommendation_count"]) for r in rows]

    def save_annotation(self, annotation: RecommendationAnnotation) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO annotations
                   (id, statement_id, recommendation_title, status, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    annotation.id,
                    annotation.statement_id,
                    annotation.recommendation_title,
                    annotation.status.value,
                    annotation.note,
                    annotation.created_at or datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_annotations(self, statement_id: str) -> list[RecommendationAnnotation]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM annotations WHERE statement_id = ?",
                (statement_id,),
            ).fetchall()
        return [
            RecommendationAnnotation(
                id=r["id"],
                statement_id=r["statement_id"],
                recommendation_title=r["recommendation_title"],
                status=AnnotationStatus(r["status"]),
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_annotation(self, annotation_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AnalysisRecord:
        return AnalysisRecord(
            statement_id=row["statement_id"],
            analyzed_at=row["analyzed_at"],
            health_score=row["health_score"],
            recommendation_count=row["recommendation_count"],
            critical_count=row["critical_count"],
            warning_count=row["warning_count"],
            info_count=row["info_count"],
            total_duration_ms=row["total_duration_ms"],
            statement_text=row["statement_text"],
            result_json=row["result_json"],
        )


def get_storage() -> SqliteStorage:
    """Return the default storage backend."""
    return SqliteStorage()
