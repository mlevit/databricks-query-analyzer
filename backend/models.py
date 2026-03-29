from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    QUERY = "query"
    EXECUTION = "execution"
    TABLE = "table"
    WAREHOUSE = "warehouse"
    STORAGE = "storage"
    DATA_MODELING = "data_modeling"


class Recommendation(BaseModel):
    severity: Severity
    category: Category
    title: str
    description: str
    action: Optional[str] = None
    snippet: Optional[str] = None
    impact: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Estimated performance impact if addressed (1=minimal, 10=transformative)",
    )
    affected_tables: list[str] = Field(default_factory=list)
    per_table_actions: dict[str, str] = Field(default_factory=dict)


class QueryMetrics(BaseModel):
    statement_id: str
    statement_text: str
    execution_status: str
    total_duration_ms: Optional[int] = None
    compilation_duration_ms: Optional[int] = None
    execution_duration_ms: Optional[int] = None
    waiting_for_compute_duration_ms: Optional[int] = None
    waiting_at_capacity_duration_ms: Optional[int] = None
    result_fetch_duration_ms: Optional[int] = None
    total_task_duration_ms: Optional[int] = None
    read_bytes: Optional[int] = None
    read_rows: Optional[int] = None
    read_files: Optional[int] = None
    read_partitions: Optional[int] = None
    pruned_files: Optional[int] = None
    produced_rows: Optional[int] = None
    spilled_local_bytes: Optional[int] = None
    read_io_cache_percent: Optional[int] = None
    from_result_cache: Optional[bool] = None
    shuffle_read_bytes: Optional[int] = None
    written_bytes: Optional[int] = None
    warehouse_id: Optional[str] = None


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    comment: Optional[str] = None


class TableInfo(BaseModel):
    full_name: str
    format: Optional[str] = None
    clustering_columns: list[str] = Field(default_factory=list)
    partition_columns: list[str] = Field(default_factory=list)
    num_files: Optional[int] = None
    size_in_bytes: Optional[int] = None
    column_count: Optional[int] = None
    columns: list[ColumnInfo] = Field(default_factory=list)
    properties: dict[str, str] = Field(default_factory=dict)
    recommendations: list[Recommendation] = Field(default_factory=list)


class PlanHighlight(BaseModel):
    line_start: int = Field(description="0-indexed first line of the highlighted region")
    line_end: int = Field(description="0-indexed last line (inclusive)")
    severity: Severity
    reason: str = Field(description="Why this part of the plan is problematic")


class PlanSummary(BaseModel):
    raw_plan: str
    scan_types: list[str] = Field(default_factory=list)
    join_types: list[str] = Field(default_factory=list)
    has_filter_pushdown: bool = False
    has_partition_pruning: bool = False
    warnings: list[str] = Field(default_factory=list)
    highlights: list[PlanHighlight] = Field(default_factory=list)


class WarehouseInfo(BaseModel):
    warehouse_id: str
    name: Optional[str] = None
    warehouse_type: Optional[str] = None
    cluster_size: Optional[str] = None
    num_clusters: Optional[int] = None
    enable_photon: Optional[bool] = None
    spot_instance_policy: Optional[str] = None
    channel: Optional[str] = None
    recommendations: list[Recommendation] = Field(default_factory=list)


class AIRewriteResult(BaseModel):
    original_sql: str
    suggested_sql: str
    explanation: str
    syntax_valid: bool = True
    syntax_errors: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    query_metrics: QueryMetrics
    tables: list[TableInfo] = Field(default_factory=list)
    plan_summary: Optional[PlanSummary] = None
    warehouse: Optional[WarehouseInfo] = None
    recommendations: list[Recommendation] = Field(default_factory=list)


class QueryExecutionMetrics(BaseModel):
    total_duration_ms: Optional[int] = None
    compilation_duration_ms: Optional[int] = None
    execution_duration_ms: Optional[int] = None
    result_fetch_duration_ms: Optional[int] = None
    total_task_duration_ms: Optional[int] = None
    read_bytes: Optional[int] = None
    read_rows: Optional[int] = None
    read_files: Optional[int] = None
    read_partitions: Optional[int] = None
    pruned_files: Optional[int] = None
    produced_rows: Optional[int] = None
    spilled_local_bytes: Optional[int] = None
    shuffle_read_bytes: Optional[int] = None
    from_result_cache: Optional[bool] = None


class QueryBenchmarkStats(BaseModel):
    elapsed_ms: int
    row_count: Optional[int] = None
    byte_count: Optional[int] = None
    status: str = "SUCCEEDED"
    error: Optional[str] = None
    metrics: Optional[QueryExecutionMetrics] = None


class BenchmarkResult(BaseModel):
    original: QueryBenchmarkStats
    suggested: QueryBenchmarkStats


# ---------------------------------------------------------------------------
# v2: Scan / batch analysis models
# ---------------------------------------------------------------------------

class ScanFilter(BaseModel):
    warehouse_id: Optional[str] = None
    user_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    table_name: Optional[str] = None
    min_duration_ms: Optional[int] = None
    max_results: int = Field(default=50, ge=1, le=200)


class QuerySummary(BaseModel):
    statement_id: str
    statement_text: str
    execution_status: str
    total_duration_ms: Optional[int] = None
    user_name: Optional[str] = None
    warehouse_id: Optional[str] = None
    health_score: int = Field(default=100, ge=0, le=100)
    recommendation_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    top_recommendations: list[str] = Field(default_factory=list)


class WorkloadPattern(BaseModel):
    pattern_type: str
    title: str
    description: str
    severity: Severity
    affected_queries: int = 0
    affected_tables: list[str] = Field(default_factory=list)
    impact: int = Field(default=5, ge=1, le=10)


class ScanResult(BaseModel):
    filters: ScanFilter
    queries: list[QuerySummary] = Field(default_factory=list)
    patterns: list[WorkloadPattern] = Field(default_factory=list)
    total_queries_scanned: int = 0
    total_duration_ms: int = 0
    scanned_at: str = ""


# ---------------------------------------------------------------------------
# v2: Health score
# ---------------------------------------------------------------------------

class HealthScore(BaseModel):
    score: int = Field(default=100, ge=0, le=100)
    breakdown: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# v2: Persistence / history models
# ---------------------------------------------------------------------------

class AnalysisRecord(BaseModel):
    statement_id: str
    analyzed_at: str
    health_score: int = 100
    recommendation_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    total_duration_ms: Optional[int] = None
    statement_text: str = ""
    result_json: Optional[str] = None


class TrendPoint(BaseModel):
    analyzed_at: str
    health_score: int
    recommendation_count: int


class AnnotationStatus(str, Enum):
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    WONT_FIX = "wont_fix"


class RecommendationAnnotation(BaseModel):
    id: str
    statement_id: str
    recommendation_title: str
    status: AnnotationStatus
    note: Optional[str] = None
    created_at: str = ""


# ---------------------------------------------------------------------------
# v2: Table health scanner
# ---------------------------------------------------------------------------

class TableHealthScanFilter(BaseModel):
    catalog: str
    schema_name: str
    table_name_pattern: Optional[str] = None
    max_results: int = Field(default=100, ge=1, le=500)


class TableHealthResult(BaseModel):
    tables: list[TableInfo] = Field(default_factory=list)
    total_scanned: int = 0
    scanned_at: str = ""


# ---------------------------------------------------------------------------
# v2: Warehouse fleet
# ---------------------------------------------------------------------------

class WarehouseFleetResult(BaseModel):
    warehouses: list[WarehouseInfo] = Field(default_factory=list)
    scanned_at: str = ""


# ---------------------------------------------------------------------------
# v2: Raw SQL analysis (no statement_id)
# ---------------------------------------------------------------------------

class RawSQLRequest(BaseModel):
    sql: str
    warehouse_id: Optional[str] = None


class RawSQLResult(BaseModel):
    recommendations: list[Recommendation] = Field(default_factory=list)
    health_score: int = 100
    tables_referenced: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# v2: Export
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    statement_id: str
    format: str = Field(default="markdown", pattern="^(markdown|html|json)$")
