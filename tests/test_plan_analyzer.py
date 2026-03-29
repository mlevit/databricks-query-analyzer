"""Tests for backend.analyzers.plan_analyzer."""

from backend.analyzers.plan_analyzer import analyze_plan


class TestScanTypes:
    def test_detects_file_scan(self):
        plan = "FileScan parquet default.test_table [...PushedFilters: []]"
        result = analyze_plan(plan)
        assert "FileScan" in result.scan_types

    def test_detects_photon_scan(self):
        plan = "PhotonScan parquet default.events [...]"
        result = analyze_plan(plan)
        assert "PhotonScan" in result.scan_types


class TestJoinTypes:
    def test_detects_broadcast_hash_join(self):
        plan = "BroadcastHashJoin [id#1], [id#2], Inner, BuildRight, false"
        result = analyze_plan(plan)
        assert "BroadcastHashJoin" in result.join_types

    def test_detects_sort_merge_join(self):
        plan = "SortMergeJoin [id#1], [id#2], Inner"
        result = analyze_plan(plan)
        assert "SortMergeJoin" in result.join_types

    def test_detects_cartesian_product(self):
        plan = "CartesianProduct"
        result = analyze_plan(plan)
        assert "CartesianProduct" in result.join_types
        assert any("Cartesian" in w for w in result.warnings)


class TestFilterPushdown:
    def test_detects_pushed_filters(self):
        plan = "PushedFilters: [IsNotNull(id)]"
        result = analyze_plan(plan)
        assert result.has_filter_pushdown is True

    def test_no_pushdown(self):
        plan = "Scan parquet default.events"
        result = analyze_plan(plan)
        assert result.has_filter_pushdown is False


class TestPartitionPruning:
    def test_detects_partition_filters(self):
        plan = "PartitionFilters: [isnotnull(date)]"
        result = analyze_plan(plan)
        assert result.has_partition_pruning is True


class TestWarnings:
    def test_cartesian_product_warning(self):
        plan = "CartesianProduct"
        result = analyze_plan(plan)
        assert any("Cartesian" in w for w in result.warnings)

    def test_scan_without_pushdown_warning(self):
        plan = """
FileScan parquet db.schema.big_table [col1, col2]
    PushedFilters: []
    ReadSchema: struct<col1:string,col2:int>
"""
        result = analyze_plan(plan)
        assert any("without filter pushdown" in w.lower() or "without pushed filters" in w.lower()
                    for w in result.warnings)


class TestHighlights:
    def test_cartesian_highlight(self):
        plan = "line0\nCartesianProduct\nline2"
        result = analyze_plan(plan)
        assert len(result.highlights) > 0
        highlight = result.highlights[0]
        assert highlight.severity.value in ("critical", "warning")


class TestRawPlan:
    def test_raw_plan_preserved(self):
        plan = "Sort [a ASC]\n  BroadcastHashJoin"
        result = analyze_plan(plan)
        assert result.raw_plan == plan

    def test_empty_plan(self):
        result = analyze_plan("")
        assert result.raw_plan == ""
        assert len(result.warnings) == 0
