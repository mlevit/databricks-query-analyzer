# Databricks SQL Architect

A Databricks App that analyzes SQL query performance and provides actionable, Databricks-specific recommendations for optimization.

Given a `statement_id`, the app inspects the query text, execution plan, runtime metrics, underlying table metadata, and warehouse configuration to surface concrete improvement suggestions — ranked by estimated performance impact.

## Features

### Analysis Engines

- **SQL Pattern Detection** — 25+ anti-pattern checks via `sqlglot` AST analysis, including `SELECT *`, correlated subqueries, implicit casts in predicates, leading wildcard `LIKE`, `NOT IN` with subqueries, unpartitioned window functions, UDF detection, legacy JSON string parsing, and more. Each finding includes the triggering SQL snippet.
- **Query Metrics Analysis** — duration breakdown, spill detection, data skipping effectiveness, shuffle volume, cache utilization, rows-scanned-to-produced ratio, parallelism efficiency, and result cache hits.
- **Execution Plan Inspection** — parses `EXPLAIN EXTENDED` output for full table scans without filter pushdown, join strategies (SortMergeJoin vs BroadcastHashJoin), exchange/shuffle counts, data skew indicators, partition pruning, fact-to-fact joins, and oversized broadcasts.
- **Table Metadata** — checks Delta table clustering, partitioning, file count/sizing, column-level analysis (wide tables, inappropriate data types, STRING columns storing JSON), VACUUM history, statistics staleness, and Hive-to-liquid-clustering migration opportunities.
- **Warehouse Configuration** — validates warehouse type, serverless compute, cluster scaling, and workload isolation.
- **Cross-Analyzer Correlations** — combines signals across engines (e.g., spill + SortMergeJoin → broadcast hint; poor pruning + unclustered table → clustering recommendation; high shuffle + misaligned clustering keys).

### Recommendations

- **Impact scoring** — each recommendation carries a 1–10 impact score estimating the performance improvement if addressed, so the highest-value fixes surface first.
- **SQL snippets** — SQL-level recommendations include the exact query fragment that triggered the check.
- **Filterable UI** — multi-select filter bar lets you drill down by severity (critical / warning / info), category (query, execution, table, warehouse, etc.), and impact tier (high / medium / low).

### Other

- **AI Query Rewrite** — uses `ai_query` with Claude to suggest an optimized version of the query, with a side-by-side diff view.
- **Benchmark** — run the original and AI-rewritten query side-by-side with live progress tracking, detailed execution metrics, and cancel support.
- **Export** — download a full analysis report as JSON or Markdown for sharing or archival.
- **On-behalf-of-user auth** — all queries run with the logged-in user's identity via `x-forwarded-access-token`, so Unity Catalog permissions (including row-level filters and column masks) are enforced automatically.
- **Shareable URLs** — analysis links include the `statement_id` so results can be shared with teammates.
- **Real-time Progress** — server-sent events stream analysis status to a progress stepper in the UI.

## Architecture

| Layer | Tech | Description |
|-------|------|-------------|
| **Frontend** | React + Vite + TypeScript | Tabbed dashboard with metrics cards, recommendations with filtering, plan viewer, table analysis, and AI rewrite panel |
| **Backend** | FastAPI + Uvicorn | REST + SSE API that orchestrates analysis modules |
| **Data** | Databricks Python SDK + SQL | Queries `system.query.history`, runs `EXPLAIN` / `DESCRIBE DETAIL` / `DESCRIBE TABLE`, calls warehouse APIs — all using on-behalf-of-user auth |
| **AI** | `ai_query` (Claude) | Rewrites queries based on detected issues |

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- Access to `system.query.history`
- A SQL warehouse configured as an app resource
- **User authorization** enabled on the workspace (Public Preview) with the `sql` scope added to the app

## Deployment

This app is designed to run on [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html).

1. **Configure the app resource** — add a SQL warehouse resource with the key `sql-warehouse` in your Databricks App settings
2. **Enable user authorization** — in the app's **Configure** step, click **+Add scope** and add the `sql` scope so the app can execute queries on behalf of the logged-in user. See [Configure authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth) for details.
3. **Deploy** — use the Databricks CLI or UI to deploy the app from this repository

The `app.yaml` maps the warehouse resource to the `DATABRICKS_WAREHOUSE_ID` environment variable automatically. All SQL queries run using the current user's identity, enforcing their Unity Catalog permissions.

## Local Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies and build
cd frontend && npm install && npm run build && cd ..

# Set environment variables
export DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>

# Start the server
uvicorn backend.main:app --reload
```

### Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
├── app.yaml                       # Databricks App config
├── backend/
│   ├── main.py                    # FastAPI app and routes
│   ├── analyzer.py                # Analysis orchestrator + cross-correlations
│   ├── db.py                      # Databricks SDK wrapper
│   ├── models.py                  # Pydantic data models
│   └── analyzers/
│       ├── sql_parser.py          # SQL AST analysis with sqlglot (25+ checks)
│       ├── query_metrics.py       # Execution metrics analysis
│       ├── plan_analyzer.py       # EXPLAIN plan parsing
│       ├── table_analyzer.py      # Table metadata + column-level checks
│       ├── warehouse_analyzer.py  # Warehouse config checks
│       └── ai_advisor.py          # AI-powered query rewrite
├── frontend/
│   ├── index.html
│   └── src/
│       ├── App.tsx                # Main app with tabbed layout
│       ├── App.css                # Styles (Databricks palette)
│       ├── api.ts                 # API client with SSE support
│       ├── types.ts               # TypeScript interfaces
│       ├── exportReport.ts        # Report generation (JSON + Markdown)
│       └── components/
│           ├── Recommendations.tsx # Recommendations with filter bar
│           ├── MetricsCards.tsx    # Query metrics dashboard
│           ├── QueryOverview.tsx   # Query text + status
│           ├── TableAnalysis.tsx   # Table metadata viewer
│           ├── PlanSummary.tsx     # Execution plan viewer
│           ├── WarehouseInfo.tsx   # Warehouse config panel
│           ├── AIRewrite.tsx       # AI rewrite with diff view
│           ├── QueryInput.tsx      # Statement ID input
│           ├── ProgressStepper.tsx # SSE progress indicator
│           └── ExportMenu.tsx      # JSON/Markdown export menu
├── tests/
│   ├── test_sql_parser.py         # SQL pattern detection tests
│   ├── test_query_metrics.py      # Metrics analysis tests
│   ├── test_table_analyzer.py     # Table check tests
│   └── test_ai_advisor.py         # AI rewrite tests
├── requirements.txt
└── package.json
```

## Checks Reference

The analyzer runs **60+ checks** across five domains. Here are some highlights:

| Domain | Examples |
|--------|----------|
| **SQL Patterns** | `SELECT *`, `UNION` without `ALL`, correlated subqueries, scalar subqueries in `SELECT`, `NOT IN` with subquery, `LIKE '%...'`, functions on filter/join columns, `CAST` in predicates, non-equi joins, `HAVING` without aggregates, deep pagination `OFFSET`, exact percentiles, UDFs, legacy JSON string parsing |
| **Execution Metrics** | Disk spill, poor file pruning, high shuffle ratio, capacity queuing, excessive scan-to-produce ratio, low parallelism, result cache misses |
| **Execution Plan** | Full scans without pushdown, SortMergeJoin candidates for broadcast, excessive exchanges/sorts, data skew, missing partition pruning, fact-to-fact joins, oversized broadcasts |
| **Table Metadata** | Missing clustering, small files, over/under-partitioning, stale statistics, non-Delta formats, wide tables, STRING columns storing dates/numbers/JSON, no VACUUM history, Hive partitioning migration |
| **Warehouse Config** | Classic warehouse type, single-cluster, non-serverless workload isolation, high concurrency with queuing, scaling events |
