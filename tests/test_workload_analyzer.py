"""Tests for backend.analyzers.workload_analyzer."""

from backend.analyzers.workload_analyzer import analyze_workload
from backend.models import (
    AnalysisResult,
    Category,
    QueryMetrics,
    Recommendation,
    Severity,
    TableInfo,
)


def _make_result(
    statement_id: str = "abc-123",
    sql: str = "SELECT * FROM t",
    duration_ms: int = 1000,
    recs: list[Recommendation] | None = None,
    tables: list[TableInfo] | None = None,
    spill: int = 0,
) -> AnalysisResult:
    return AnalysisResult(
        query_metrics=QueryMetrics(
            statement_id=statement_id,
            statement_text=sql,
            execution_status="FINISHED",
            total_duration_ms=duration_ms,
            spilled_local_bytes=spill,
        ),
        tables=tables or [],
        recommendations=recs or [],
    )


class TestRepeatedAntipatterns:
    def test_detects_repeated_check(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                recs=[
                    Recommendation(
                        severity=Severity.INFO,
                        category=Category.QUERY,
                        title="SELECT * used",
                        description="desc",
                        impact=3,
                    )
                ],
            )
            for i in range(10)
        ]
        patterns = analyze_workload(results)
        titles = [p.title for p in patterns]
        assert any("SELECT * used" in t for t in titles)

    def test_no_pattern_for_low_occurrence(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                recs=[
                    Recommendation(
                        severity=Severity.INFO,
                        category=Category.QUERY,
                        title="SELECT * used",
                        description="desc",
                        impact=3,
                    )
                ] if i == 0 else [],
            )
            for i in range(10)
        ]
        patterns = analyze_workload(results)
        repeated = [p for p in patterns if p.pattern_type == "repeated_antipattern"]
        assert len(repeated) == 0


class TestHotTables:
    def test_detects_hot_table(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                duration_ms=5000,
                tables=[TableInfo(full_name="db.schema.hot_table")],
            )
            for i in range(5)
        ]
        patterns = analyze_workload(results)
        hot = [p for p in patterns if p.pattern_type == "hot_table"]
        assert len(hot) >= 1
        assert "hot_table" in hot[0].affected_tables[0]


class TestRedundantQueries:
    def test_detects_near_duplicates(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                sql=f"SELECT * FROM t WHERE id = {i}",
            )
            for i in range(5)
        ]
        patterns = analyze_workload(results)
        redundant = [p for p in patterns if p.pattern_type == "redundant_query"]
        assert len(redundant) >= 1


class TestWidespreadSpill:
    def test_detects_widespread_spill(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                spill=200 * 1024 * 1024,
            )
            for i in range(8)
        ]
        patterns = analyze_workload(results)
        spill_patterns = [p for p in patterns if p.pattern_type == "widespread_spill"]
        assert len(spill_patterns) == 1

    def test_no_spill_pattern_when_few(self):
        results = [
            _make_result(
                statement_id=f"stmt-{i}",
                spill=200 * 1024 * 1024 if i == 0 else 0,
            )
            for i in range(10)
        ]
        patterns = analyze_workload(results)
        spill_patterns = [p for p in patterns if p.pattern_type == "widespread_spill"]
        assert len(spill_patterns) == 0


class TestEmptyInput:
    def test_empty_list(self):
        patterns = analyze_workload([])
        assert patterns == []
