"""Tests for backend.analyzer orchestration, health score, and grouping."""

from backend.analyzer import (
    _deduplicate_clustering_recs,
    _group_recommendations,
    compute_health_score,
    run_sql_analysis,
)
from backend.models import Category, Recommendation, Severity


class TestHealthScore:
    def test_no_recommendations(self):
        hs = compute_health_score([])
        assert hs.score == 100
        assert hs.breakdown == {}

    def test_single_info(self):
        recs = [
            Recommendation(
                severity=Severity.INFO,
                category=Category.QUERY,
                title="Test",
                description="desc",
                impact=3,
            )
        ]
        hs = compute_health_score(recs)
        assert 90 <= hs.score <= 100
        assert hs.breakdown["info"] == 1

    def test_critical_recs_lower_score(self):
        recs = [
            Recommendation(
                severity=Severity.CRITICAL,
                category=Category.QUERY,
                title="Critical issue",
                description="desc",
                impact=10,
            )
        ]
        hs = compute_health_score(recs)
        assert hs.score < 100
        assert hs.breakdown["critical"] == 1

    def test_many_recs_give_low_score(self):
        recs = [
            Recommendation(
                severity=Severity.CRITICAL,
                category=Category.QUERY,
                title=f"Issue {i}",
                description="desc",
                impact=10,
            )
            for i in range(10)
        ]
        hs = compute_health_score(recs)
        assert hs.score == 0


class TestGroupRecommendations:
    def test_no_affected_tables_pass_through(self):
        recs = [
            Recommendation(
                severity=Severity.INFO,
                category=Category.QUERY,
                title="SELECT * used",
                description="desc",
                impact=3,
            )
        ]
        result = _group_recommendations(recs)
        assert len(result) == 1
        assert result[0].title == "SELECT * used"

    def test_merge_same_title(self):
        recs = [
            Recommendation(
                severity=Severity.WARNING,
                category=Category.TABLE,
                title="No clustering configured",
                description="desc",
                impact=6,
                affected_tables=["db.schema.table_a"],
                per_table_actions={"db.schema.table_a": "ALTER TABLE db.schema.table_a CLUSTER BY AUTO;"},
            ),
            Recommendation(
                severity=Severity.WARNING,
                category=Category.TABLE,
                title="No clustering configured",
                description="desc",
                impact=7,
                affected_tables=["db.schema.table_b"],
                per_table_actions={"db.schema.table_b": "ALTER TABLE db.schema.table_b CLUSTER BY AUTO;"},
            ),
        ]
        result = _group_recommendations(recs)
        assert len(result) == 1
        merged = result[0]
        assert "db.schema.table_a" in merged.affected_tables
        assert "db.schema.table_b" in merged.affected_tables
        assert merged.impact == 7  # max

    def test_different_titles_not_merged(self):
        recs = [
            Recommendation(
                severity=Severity.WARNING,
                category=Category.TABLE,
                title="No clustering configured",
                description="desc",
                impact=6,
                affected_tables=["t1"],
            ),
            Recommendation(
                severity=Severity.WARNING,
                category=Category.TABLE,
                title="Small file problem",
                description="desc",
                impact=5,
                affected_tables=["t1"],
            ),
        ]
        result = _group_recommendations(recs)
        assert len(result) == 2


class TestDeduplicateClusteringRecs:
    def test_removes_poor_data_skipping_when_clustering_exists(self):
        recs = [
            Recommendation(
                severity=Severity.WARNING,
                category=Category.TABLE,
                title="No clustering configured",
                description="desc",
                impact=7,
            ),
            Recommendation(
                severity=Severity.WARNING,
                category=Category.EXECUTION,
                title="Poor data skipping",
                description="desc",
                impact=6,
            ),
        ]
        result = _deduplicate_clustering_recs(recs)
        titles = [r.title for r in result]
        assert "Poor data skipping" not in titles
        assert "No clustering configured" in titles

    def test_keeps_poor_data_skipping_without_clustering_rec(self):
        recs = [
            Recommendation(
                severity=Severity.WARNING,
                category=Category.EXECUTION,
                title="Poor data skipping",
                description="desc",
                impact=6,
            ),
        ]
        result = _deduplicate_clustering_recs(recs)
        assert len(result) == 1


class TestRunSqlAnalysis:
    def test_basic_select_star(self):
        recs, table_list = run_sql_analysis("SELECT * FROM my_db.my_schema.my_table")
        titles = [r.title for r in recs]
        assert "SELECT * used" in titles
        assert "my_db.my_schema.my_table" in table_list

    def test_no_issues_for_clean_query(self):
        recs, _table_list = run_sql_analysis("SELECT id, name FROM t WHERE id = 1")
        critical_count = sum(1 for r in recs if r.severity == Severity.CRITICAL)
        assert critical_count == 0

    def test_cross_join_detected(self):
        recs, _ = run_sql_analysis("SELECT * FROM a CROSS JOIN b")
        titles = [r.title for r in recs]
        assert "Cross join detected" in titles
