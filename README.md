# Databricks Query Performance Analyzer

A Databricks App that analyzes SQL query performance and provides actionable, Databricks-specific recommendations for optimization.

Given a `statement_id`, the app inspects the query text, execution plan, runtime metrics, underlying table metadata, and warehouse configuration to surface concrete improvement suggestions — ranked by estimated performance impact.

## Features

### Analysis Engines

- **SQL Pattern Detection** — 25+ anti-pattern checks via `sqlglot` AST analysis, including `SELECT *`, correlated subqueries, implicit casts in predicates, leading wildcard `LIKE`, `NOT IN` with subqueries, unpartitioned window functions, UDF detection, legacy JSON string parsing, and more. Each finding includes the triggering SQL snippet.
- **Query Metrics Analysis** — duration breakdown, spill detection, data skipping effectiveness, shuffle volume, cache utilization, rows-scanned-to-produced ratio, parallelism efficiency, and result cache hits.
- **Execution Plan Inspection** — parses `EXPLAIN EXTENDED` output for full table scans without filter pushdown, join strategies (SortMergeJoin vs BroadcastHashJoin), exchange/shuffle counts, data skew indicators, partition pruning, fact-to-fact joins, and oversized broadcasts.
- **Table Metadata** — checks Delta table clustering, partitioning, file count/sizing, column-level analysis (wide tables, inappropriate data types, STRING columns storing JSON), VACUUM history, statistics staleness, and Hive-to-liquid-clustering migration opportunities.
- **Warehouse Configuration** — validates Photon enablement, warehouse type, serverless compute, cluster scaling, and workload isolation.
- **Cross-Analyzer Correlations** — combines signals across engines (e.g., spill + SortMergeJoin → broadcast hint; poor pruning + unclustered table → clustering recommendation; high shuffle + misaligned clustering keys).

### Recommendations

- **Impact scoring** — each recommendation carries a 1–10 impact score estimating the performance improvement if addressed, so the highest-value fixes surface first.
- **Health score** — a 0–100 composite score summarising overall query health, enabling at-a-glance comparison and trending over time.
- **SQL snippets** — SQL-level recommendations include the exact query fragment that triggered the check.
- **Filterable UI** — multi-select filter bar lets you drill down by severity (critical / warning / info), category (query, execution, table, warehouse, etc.), and impact tier (high / medium / low).
- **Annotations** — mark recommendations as "acknowledged", "in progress", or "won't fix" to track optimization work.

### Workload Intelligence (v2)

- **Batch Scanner** — scan multiple queries at once by warehouse, user, time range, or table name. The scanner runs the full analysis pipeline on each query and surfaces workload-level patterns.
- **Workload Patterns** — detects recurring anti-patterns across queries, hot tables, near-duplicate queries, and widespread performance issues.
- **Trending Dashboard** — track health scores and recommendation counts over time with interactive charts.
- **Table Health Scanner** — scan all tables in a catalog/schema for metadata issues without needing a specific query.
- **Warehouse Fleet View** — audit all SQL warehouses for configuration issues (Photon, serverless, sizing).

### SQL Analyzer

- **Raw SQL Analysis** — paste SQL directly to check for anti-patterns without needing a `statement_id` or execution history. Useful for pre-deployment checks and CI/CD integration.

### Other

- **AI Query Rewrite** — uses `ai_query` with Claude to suggest an optimized version of the query, with a side-by-side diff view and benchmarking.
- **Export** — download analysis results as Markdown, HTML, or JSON for sharing and documentation.
- **Shareable URLs** — analysis links include the `statement_id` so results can be shared with teammates.
- **Real-time Progress** — server-sent events stream analysis status to a progress stepper in the UI.
- **Dark Mode** — toggle between light and dark themes, with automatic detection of system preference.

## Architecture

| Layer | Tech | Description |
|-------|------|-------------|
| **Frontend** | React + Vite + TypeScript + React Router | Multi-page dashboard with workload scanning, trends, table health, warehouse fleet, and single-query analysis |
| **Backend** | FastAPI + Uvicorn | REST + SSE API that orchestrates analysis modules |
| **Data** | Databricks Python SDK + SQL | Queries `system.query.history`, runs `EXPLAIN` / `DESCRIBE DETAIL` / `DESCRIBE TABLE`, calls warehouse APIs |
| **AI** | `ai_query` (Claude) | Rewrites queries based on detected issues |
| **Storage** | SQLite (local) | Persists analysis history, health scores, and annotations |
| **Charts** | Recharts | Health score trends and recommendation count visualisations |

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- Access to `system.query.history`
- A SQL warehouse configured as an app resource

## Deployment

This app is designed to run on [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html).

1. **Configure the app resource** — add a SQL warehouse resource with the key `sql-warehouse` in your Databricks App settings
2. **Deploy** — use the Databricks CLI or UI to deploy the app from this repository

The `app.yaml` maps the warehouse resource to the `DATABRICKS_WAREHOUSE_ID` environment variable automatically.

## Local Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies and build
npm install
npm run build

# Set environment variables
export DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>

# Start the server
uvicorn backend.main:app --reload
```

For frontend development with hot reload:

```bash
# Terminal 1: Start the backend
uvicorn backend.main:app --reload

# Terminal 2: Start the frontend dev server (proxies /api to backend)
npm run dev
```

### Running Tests

```bash
# Backend tests
pip install pytest
python -m pytest tests/ -v

# Frontend tests
npm test

# E2E tests (requires Playwright)
npx playwright install
npm run test:e2e
```

## Project Structure

```
├── app.yaml                       # Databricks App config
├── backend/
│   ├── main.py                    # FastAPI app and routes
│   ├── analyzer.py                # Analysis orchestrator + cross-correlations + batch
│   ├── db.py                      # Databricks SDK wrapper
│   ├── models.py                  # Pydantic data models
│   ├── storage.py                 # Persistence layer (SQLite)
│   └── analyzers/
│       ├── sql_parser.py          # SQL AST analysis with sqlglot (25+ checks)
│       ├── query_metrics.py       # Execution metrics analysis
│       ├── plan_analyzer.py       # EXPLAIN plan parsing
│       ├── table_analyzer.py      # Table metadata + column-level checks
│       ├── warehouse_analyzer.py  # Warehouse config checks
│       ├── workload_analyzer.py   # Cross-query workload pattern detection
│       └── ai_advisor.py          # AI-powered query rewrite
├── frontend/
│   ├── index.html
│   ├── vitest.config.ts           # Frontend test configuration
│   └── src/
│       ├── App.tsx                # Root layout with navigation + dark mode
│       ├── main.tsx               # Router setup
│       ├── api.ts                 # API client with SSE support
│       ├── types.ts               # TypeScript interfaces
│       ├── utils.ts               # Formatting helpers
│       ├── pages/
│       │   ├── AnalyzePage.tsx    # Single-query analysis (statement_id)
│       │   ├── SqlAnalyzePage.tsx # Raw SQL analysis
│       │   ├── ScanPage.tsx       # Workload batch scanner
│       │   ├── TrendsPage.tsx     # Health score trends + history
│       │   ├── TablesPage.tsx     # Table health scanner
│       │   └── WarehousesPage.tsx # Warehouse fleet view
│       ├── components/
│       │   ├── Recommendations.tsx # Recommendations with filter bar
│       │   ├── MetricsCards.tsx    # Query metrics dashboard
│       │   ├── QueryOverview.tsx   # Query text + status
│       │   ├── TableAnalysis.tsx   # Table metadata viewer
│       │   ├── PlanSummary.tsx     # Execution plan viewer
│       │   ├── WarehouseInfo.tsx   # Warehouse config panel
│       │   ├── AIRewrite.tsx       # AI rewrite with diff view
│       │   ├── QueryInput.tsx      # Statement ID input
│       │   ├── ProgressStepper.tsx # SSE progress indicator
│       │   ├── FullScreenModal.tsx # Full-screen overlay
│       │   └── shared/
│       │       └── recommendation.tsx # Shared recommendation card
│       └── __tests__/
│           ├── setup.ts           # Test setup
│           ├── utils.test.ts      # Utility function tests
│           └── types.test.ts      # Type contract tests
├── tests/
│   ├── test_sql_parser.py         # SQL pattern detection tests
│   ├── test_query_metrics.py      # Metrics analysis tests
│   ├── test_table_analyzer.py     # Table check tests
│   ├── test_ai_advisor.py         # AI rewrite tests
│   ├── test_analyzer.py           # Orchestration + health score tests
│   ├── test_workload_analyzer.py  # Workload pattern tests
│   ├── test_storage.py            # Persistence layer tests
│   ├── test_plan_analyzer.py      # Execution plan tests
│   └── test_warehouse_analyzer.py # Warehouse config tests
├── e2e/
│   └── navigation.spec.ts        # Playwright E2E tests
├── playwright.config.ts           # E2E test configuration
├── requirements.txt
└── package.json
```

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analyze/{statement_id}/stream` | SSE streaming analysis |
| GET | `/api/analyze/{statement_id}` | Non-streaming analysis |
| POST | `/api/analyze/sql` | Analyze raw SQL text |
| POST | `/api/rewrite/{statement_id}` | AI-powered query rewrite |
| POST | `/api/benchmark` | Compare original vs rewritten query |
| POST | `/api/scan/stream` | SSE streaming batch scan |
| POST | `/api/scan` | Non-streaming batch scan |
| GET | `/api/history` | Analysis history |
| GET | `/api/trends` | Health score trends |
| POST | `/api/annotations` | Create recommendation annotation |
| GET | `/api/annotations/{statement_id}` | Get annotations |
| DELETE | `/api/annotations/{annotation_id}` | Delete annotation |
| POST | `/api/tables/scan` | Scan table health |
| GET | `/api/warehouses` | Warehouse fleet scan |
| POST | `/api/export` | Export analysis (markdown/html/json) |
| GET | `/api/health` | Health check |

## Checks Reference

The analyzer runs **60+ checks** across five domains. Here are some highlights:

| Domain | Examples |
|--------|----------|
| **SQL Patterns** | `SELECT *`, `UNION` without `ALL`, correlated subqueries, scalar subqueries in `SELECT`, `NOT IN` with subquery, `LIKE '%...'`, functions on filter/join columns, `CAST` in predicates, non-equi joins, `HAVING` without aggregates, deep pagination `OFFSET`, exact percentiles, UDFs, legacy JSON string parsing |
| **Execution Metrics** | Disk spill, poor file pruning, high shuffle ratio, capacity queuing, excessive scan-to-produce ratio, low parallelism, result cache misses |
| **Execution Plan** | Full scans without pushdown, SortMergeJoin candidates for broadcast, excessive exchanges/sorts, data skew, missing partition pruning, fact-to-fact joins, oversized broadcasts |
| **Table Metadata** | Missing clustering, small files, over/under-partitioning, stale statistics, non-Delta formats, wide tables, STRING columns storing dates/numbers/JSON, no VACUUM history, Hive partitioning migration |
| **Warehouse Config** | Photon disabled, classic warehouse type, single-cluster, non-serverless workload isolation |
| **Workload Patterns** | Recurring anti-patterns, hot tables, near-duplicate queries, widespread disk spill |
