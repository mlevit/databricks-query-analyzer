export type Severity = "critical" | "warning" | "info";
export type Category = "query" | "execution" | "table" | "warehouse" | "storage" | "data_modeling";

export interface Recommendation {
  severity: Severity;
  category: Category;
  title: string;
  description: string;
  action?: string;
  snippet?: string;
  impact: number;
  affected_tables?: string[];
  per_table_actions?: Record<string, string>;
}

export interface QueryMetrics {
  statement_id: string;
  statement_text: string;
  execution_status: string;
  total_duration_ms: number | null;
  compilation_duration_ms: number | null;
  execution_duration_ms: number | null;
  waiting_for_compute_duration_ms: number | null;
  waiting_at_capacity_duration_ms: number | null;
  result_fetch_duration_ms: number | null;
  total_task_duration_ms: number | null;
  read_bytes: number | null;
  read_rows: number | null;
  read_files: number | null;
  read_partitions: number | null;
  pruned_files: number | null;
  produced_rows: number | null;
  spilled_local_bytes: number | null;
  read_io_cache_percent: number | null;
  from_result_cache: boolean | null;
  shuffle_read_bytes: number | null;
  written_bytes: number | null;
  warehouse_id: string | null;
}

export interface TableInfo {
  full_name: string;
  format: string | null;
  clustering_columns: string[];
  partition_columns: string[];
  num_files: number | null;
  size_in_bytes: number | null;
  column_count: number | null;
  properties: Record<string, string>;
  recommendations: Recommendation[];
}

export interface PlanHighlight {
  line_start: number;
  line_end: number;
  severity: Severity;
  reason: string;
}

export interface PlanSummary {
  raw_plan: string;
  scan_types: string[];
  join_types: string[];
  has_filter_pushdown: boolean;
  has_partition_pruning: boolean;
  warnings: string[];
  highlights: PlanHighlight[];
}

export interface WarehouseInfo {
  warehouse_id: string;
  name: string | null;
  warehouse_type: string | null;
  cluster_size: string | null;
  num_clusters: number | null;
  enable_photon: boolean | null;
  spot_instance_policy: string | null;
  channel: string | null;
  recommendations: Recommendation[];
}

export interface AnalysisResult {
  query_metrics: QueryMetrics;
  tables: TableInfo[];
  plan_summary: PlanSummary | null;
  warehouse: WarehouseInfo | null;
  recommendations: Recommendation[];
}

export interface AIRewriteResult {
  original_sql: string;
  suggested_sql: string;
  explanation: string;
  syntax_valid: boolean;
  syntax_errors: string[];
}

export interface QueryExecutionMetrics {
  total_duration_ms: number | null;
  compilation_duration_ms: number | null;
  execution_duration_ms: number | null;
  result_fetch_duration_ms: number | null;
  total_task_duration_ms: number | null;
  read_bytes: number | null;
  read_rows: number | null;
  read_files: number | null;
  read_partitions: number | null;
  pruned_files: number | null;
  produced_rows: number | null;
  spilled_local_bytes: number | null;
  shuffle_read_bytes: number | null;
  from_result_cache: boolean | null;
}

export interface QueryBenchmarkStats {
  elapsed_ms: number;
  row_count: number | null;
  byte_count: number | null;
  status: string;
  error: string | null;
  metrics: QueryExecutionMetrics | null;
}

export interface BenchmarkResult {
  original: QueryBenchmarkStats;
  suggested: QueryBenchmarkStats;
}

// ---------------------------------------------------------------------------
// v2: Scan / batch analysis
// ---------------------------------------------------------------------------

export interface ScanFilter {
  warehouse_id?: string;
  user_name?: string;
  start_time?: string;
  end_time?: string;
  table_name?: string;
  min_duration_ms?: number;
  max_results?: number;
}

export interface QuerySummary {
  statement_id: string;
  statement_text: string;
  execution_status: string;
  total_duration_ms: number | null;
  user_name: string | null;
  warehouse_id: string | null;
  health_score: number;
  recommendation_count: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  top_recommendations: string[];
}

export interface WorkloadPattern {
  pattern_type: string;
  title: string;
  description: string;
  severity: Severity;
  affected_queries: number;
  affected_tables: string[];
  impact: number;
}

export interface ScanResult {
  filters: ScanFilter;
  queries: QuerySummary[];
  patterns: WorkloadPattern[];
  total_queries_scanned: number;
  total_duration_ms: number;
  scanned_at: string;
}

// ---------------------------------------------------------------------------
// v2: Health & trending
// ---------------------------------------------------------------------------

export interface HealthScore {
  score: number;
  breakdown: Record<string, number>;
}

export interface AnalysisRecord {
  statement_id: string;
  analyzed_at: string;
  health_score: number;
  recommendation_count: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  total_duration_ms: number | null;
  statement_text: string;
}

export interface TrendPoint {
  analyzed_at: string;
  health_score: number;
  recommendation_count: number;
}

// ---------------------------------------------------------------------------
// v2: Annotations
// ---------------------------------------------------------------------------

export type AnnotationStatus = "acknowledged" | "in_progress" | "wont_fix";

export interface RecommendationAnnotation {
  id: string;
  statement_id: string;
  recommendation_title: string;
  status: AnnotationStatus;
  note: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// v2: Table health
// ---------------------------------------------------------------------------

export interface TableHealthScanFilter {
  catalog: string;
  schema_name: string;
  table_name_pattern?: string;
  max_results?: number;
}

export interface TableHealthResult {
  tables: TableInfo[];
  total_scanned: number;
  scanned_at: string;
}

// ---------------------------------------------------------------------------
// v2: Warehouse fleet
// ---------------------------------------------------------------------------

export interface WarehouseFleetResult {
  warehouses: WarehouseInfo[];
  scanned_at: string;
}

// ---------------------------------------------------------------------------
// v2: Raw SQL analysis
// ---------------------------------------------------------------------------

export interface RawSQLResult {
  recommendations: Recommendation[];
  health_score: number;
  tables_referenced: string[];
}
