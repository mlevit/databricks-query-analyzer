"""Tests for backend.storage persistence layer."""

import pytest

from backend.models import (
    AnalysisResult,
    AnnotationStatus,
    QueryMetrics,
    Recommendation,
    RecommendationAnnotation,
    Severity,
    Category,
)
from backend.storage import SqliteStorage


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    return SqliteStorage(db_path=db_path)


def _make_result(sid: str = "test-001") -> AnalysisResult:
    return AnalysisResult(
        query_metrics=QueryMetrics(
            statement_id=sid,
            statement_text="SELECT * FROM t",
            execution_status="FINISHED",
            total_duration_ms=1500,
        ),
        recommendations=[
            Recommendation(
                severity=Severity.WARNING,
                category=Category.QUERY,
                title="SELECT * used",
                description="desc",
                impact=3,
            ),
            Recommendation(
                severity=Severity.CRITICAL,
                category=Category.EXECUTION,
                title="Cross join",
                description="desc",
                impact=10,
            ),
        ],
    )


class TestSaveAndRetrieve:
    def test_save_and_get_history(self, storage):
        result = _make_result()
        storage.save_analysis(result, health_score=65)
        history = storage.get_history("test-001")
        assert len(history) == 1
        assert history[0].statement_id == "test-001"
        assert history[0].health_score == 65
        assert history[0].recommendation_count == 2
        assert history[0].critical_count == 1
        assert history[0].warning_count == 1

    def test_multiple_analyses(self, storage):
        for i in range(3):
            storage.save_analysis(_make_result("test-001"), health_score=60 + i * 10)
        history = storage.get_history("test-001")
        assert len(history) == 3

    def test_get_all_history(self, storage):
        storage.save_analysis(_make_result("stmt-a"), 80)
        storage.save_analysis(_make_result("stmt-b"), 70)
        all_h = storage.get_all_history(limit=10)
        assert len(all_h) == 2


class TestTrending:
    def test_get_trend(self, storage):
        for i in range(3):
            storage.save_analysis(_make_result("test-001"), health_score=50 + i * 10)
        trend = storage.get_trend("test-001")
        assert len(trend) == 3
        assert trend[0].health_score == 50
        assert trend[2].health_score == 70

    def test_global_trend(self, storage):
        storage.save_analysis(_make_result("a"), 80)
        storage.save_analysis(_make_result("b"), 60)
        trend = storage.get_global_trend(limit=10)
        assert len(trend) == 2


class TestAnnotations:
    def test_save_and_retrieve(self, storage):
        ann = RecommendationAnnotation(
            id="ann-1",
            statement_id="test-001",
            recommendation_title="SELECT * used",
            status=AnnotationStatus.ACKNOWLEDGED,
            note="Will fix later",
            created_at="2024-01-01T00:00:00Z",
        )
        storage.save_annotation(ann)
        result = storage.get_annotations("test-001")
        assert len(result) == 1
        assert result[0].status == AnnotationStatus.ACKNOWLEDGED
        assert result[0].note == "Will fix later"

    def test_delete_annotation(self, storage):
        ann = RecommendationAnnotation(
            id="ann-2",
            statement_id="test-001",
            recommendation_title="Test",
            status=AnnotationStatus.IN_PROGRESS,
            created_at="2024-01-01T00:00:00Z",
        )
        storage.save_annotation(ann)
        assert storage.delete_annotation("ann-2") is True
        assert storage.delete_annotation("nonexistent") is False
        assert len(storage.get_annotations("test-001")) == 0

    def test_upsert_annotation(self, storage):
        ann = RecommendationAnnotation(
            id="ann-3",
            statement_id="test-001",
            recommendation_title="Test",
            status=AnnotationStatus.ACKNOWLEDGED,
            created_at="2024-01-01T00:00:00Z",
        )
        storage.save_annotation(ann)
        ann.status = AnnotationStatus.WONT_FIX
        storage.save_annotation(ann)
        result = storage.get_annotations("test-001")
        assert len(result) == 1
        assert result[0].status == AnnotationStatus.WONT_FIX
