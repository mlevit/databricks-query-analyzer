"""Tests for backend.analyzers.warehouse_analyzer."""

from unittest.mock import patch

from backend.analyzers.warehouse_analyzer import analyze_warehouse


def _mock_config(**overrides):
    base = {
        "warehouse_id": "wh-123",
        "name": "Test Warehouse",
        "warehouse_type": "PRO",
        "cluster_size": "Medium",
        "num_clusters": 2,
        "enable_photon": True,
        "enable_serverless_compute": True,
        "spot_instance_policy": "COST_OPTIMIZED",
        "channel": "CHANNEL_NAME_CURRENT",
    }
    base.update(overrides)
    return base


class TestPhotonCheck:
    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_photon_disabled(self, mock_config):
        mock_config.return_value = _mock_config(enable_photon=False)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Photon not enabled" in titles

    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_photon_enabled(self, mock_config):
        mock_config.return_value = _mock_config(enable_photon=True)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Photon not enabled" not in titles


class TestWarehouseType:
    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_classic_type(self, mock_config):
        mock_config.return_value = _mock_config(warehouse_type="CLASSIC")
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Classic warehouse type" in titles

    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_pro_type_no_warning(self, mock_config):
        mock_config.return_value = _mock_config(warehouse_type="PRO")
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Classic warehouse type" not in titles


class TestSingleCluster:
    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_single_cluster(self, mock_config):
        mock_config.return_value = _mock_config(num_clusters=1)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Single-cluster warehouse" in titles

    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_multi_cluster_no_warning(self, mock_config):
        mock_config.return_value = _mock_config(num_clusters=3)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Single-cluster warehouse" not in titles


class TestWorkloadIsolation:
    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_non_serverless_gets_isolation_rec(self, mock_config):
        mock_config.return_value = _mock_config(enable_serverless_compute=False)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Consider workload isolation" in titles

    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_serverless_no_isolation_rec(self, mock_config):
        mock_config.return_value = _mock_config(enable_serverless_compute=True)
        result = analyze_warehouse("wh-123")
        titles = [r.title for r in result.recommendations]
        assert "Consider workload isolation" not in titles


class TestFailedFetch:
    @patch("backend.analyzers.warehouse_analyzer.get_warehouse_config")
    def test_returns_empty_on_error(self, mock_config):
        mock_config.side_effect = RuntimeError("API error")
        result = analyze_warehouse("wh-123")
        assert result.warehouse_id == "wh-123"
        assert len(result.recommendations) == 0
