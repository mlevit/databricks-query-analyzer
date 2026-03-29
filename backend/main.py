import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.analyzer import (
    STEPS,
    compute_health_score,
    run_analysis,
    run_batch_analysis,
    run_sql_analysis,
)
from backend.analyzers.ai_advisor import rewrite_query
from backend.analyzers.table_analyzer import analyze_tables
from backend.analyzers.warehouse_analyzer import analyze_warehouse
from backend.analyzers.sql_parser import parse_query
from backend.db import execute_sql_with_metrics, list_tables_in_schema, list_warehouses
from backend.models import (
    AIRewriteResult,
    AnalysisRecord,
    AnalysisResult,
    AnnotationStatus,
    BenchmarkResult,
    ExportRequest,
    HealthScore,
    QueryBenchmarkStats,
    QueryExecutionMetrics,
    RawSQLRequest,
    RawSQLResult,
    RecommendationAnnotation,
    ScanFilter,
    ScanResult,
    TableHealthResult,
    TableHealthScanFilter,
    TrendPoint,
    WarehouseFleetResult,
    WarehouseInfo,
)
from backend.storage import get_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Databricks Query Performance Analyzer")

# ---------------------------------------------------------------------------
# Bounded TTL cache for analysis results
# ---------------------------------------------------------------------------
_CACHE_MAX_SIZE = 200
_CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

_analysis_cache: OrderedDict[str, tuple[float, AnalysisResult]] = OrderedDict()


def _cache_get(key: str) -> AnalysisResult | None:
    entry = _analysis_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _analysis_cache.pop(key, None)
        return None
    _analysis_cache.move_to_end(key)
    return result


def _cache_put(key: str, result: AnalysisResult) -> None:
    _analysis_cache[key] = (time.time(), result)
    _analysis_cache.move_to_end(key)
    while len(_analysis_cache) > _CACHE_MAX_SIZE:
        _analysis_cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
_STATEMENT_ID_RE = re.compile(r"^[0-9a-fA-F\-]{1,128}$")


def _validate_statement_id(statement_id: str) -> None:
    if not _STATEMENT_ID_RE.match(statement_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid statement_id format. Expected a UUID-like identifier.",
        )


# ---------------------------------------------------------------------------
# SSE streaming analysis (sends progress events, then final result)
# ---------------------------------------------------------------------------
@app.get("/api/analyze/{statement_id}/stream")
async def analyze_stream(statement_id: str):
    _validate_statement_id(statement_id)

    q: queue.Queue[dict | None] = queue.Queue()

    def on_progress(step: int, label: str, status: str) -> None:
        q.put({"step": step, "total": len(STEPS), "label": label, "status": status})

    def run() -> None:
        try:
            result = run_analysis(statement_id, on_progress=on_progress)
            _cache_put(statement_id, result)
            try:
                hs = compute_health_score(result.recommendations)
                get_storage().save_analysis(result, hs.score)
            except Exception:
                logger.warning("Failed to persist analysis for %s", statement_id, exc_info=True)
            q.put({"event": "result", "data": result.model_dump(mode="json")})
        except ValueError as exc:
            q.put({"event": "error", "detail": str(exc), "code": 404})
        except Exception:
            logger.exception("Analysis failed for %s", statement_id)
            q.put({"event": "error", "detail": "Internal analysis error", "code": 500})
        finally:
            q.put(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    def event_generator():
        while True:
            msg = q.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Non-streaming fallback (kept for simplicity / direct API calls)
# ---------------------------------------------------------------------------
@app.get("/api/analyze/{statement_id}", response_model=AnalysisResult)
async def analyze(statement_id: str):
    _validate_statement_id(statement_id)
    try:
        result = run_analysis(statement_id)
        _cache_put(statement_id, result)
        try:
            hs = compute_health_score(result.recommendations)
            get_storage().save_analysis(result, hs.score)
        except Exception:
            logger.warning("Failed to persist analysis for %s", statement_id, exc_info=True)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        logger.exception("Analysis failed for %s", statement_id)
        raise HTTPException(status_code=500, detail="Internal analysis error") from None


class RewriteRequest(BaseModel):
    custom_instruction: str | None = None


@app.post("/api/rewrite/{statement_id}", response_model=AIRewriteResult)
async def rewrite(statement_id: str, req: RewriteRequest | None = None):
    _validate_statement_id(statement_id)

    analysis = _cache_get(statement_id)
    if analysis is None:
        try:
            analysis = run_analysis(statement_id)
            _cache_put(statement_id, analysis)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception:
            logger.exception("Analysis failed for %s", statement_id)
            raise HTTPException(status_code=500, detail="Internal analysis error") from None

    custom_instruction = req.custom_instruction if req else None

    try:
        return rewrite_query(analysis, custom_instruction=custom_instruction)
    except Exception:
        logger.exception("AI rewrite failed for %s", statement_id)
        raise HTTPException(status_code=500, detail="AI rewrite failed") from None


class BenchmarkRequest(BaseModel):
    original_sql: str
    suggested_sql: str
    warehouse_id: str | None = None


@app.post("/api/benchmark", response_model=BenchmarkResult)
async def benchmark(req: BenchmarkRequest):
    """Run both the original and suggested queries and return execution stats."""
    wid = req.warehouse_id or None

    try:
        original_stats = execute_sql_with_metrics(req.original_sql, warehouse_id=wid)
    except Exception:
        logger.exception("Benchmark: original query execution failed")
        raise HTTPException(status_code=500, detail="Failed to execute original query") from None

    try:
        suggested_stats = execute_sql_with_metrics(req.suggested_sql, warehouse_id=wid)
    except Exception:
        logger.exception("Benchmark: suggested query execution failed")
        raise HTTPException(status_code=500, detail="Failed to execute suggested query") from None

    def _to_benchmark_stats(raw: dict) -> QueryBenchmarkStats:
        metrics_data = raw.pop("metrics", None)
        stats = QueryBenchmarkStats(**raw)
        if metrics_data:
            stats.metrics = QueryExecutionMetrics(**metrics_data)
        return stats

    return BenchmarkResult(
        original=_to_benchmark_stats(original_stats),
        suggested=_to_benchmark_stats(suggested_stats),
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# v2: Batch / scan analysis
# ---------------------------------------------------------------------------

@app.post("/api/scan/stream")
async def scan_stream(scan_filter: ScanFilter):
    q: queue.Queue[dict | None] = queue.Queue()

    def on_progress(step: int, label: str, status: str) -> None:
        q.put({"step": step, "total": 3, "label": label, "status": status})

    def run() -> None:
        try:
            result = run_batch_analysis(scan_filter, on_progress=on_progress)
            q.put({"event": "result", "data": result.model_dump(mode="json")})
        except Exception:
            logger.exception("Batch scan failed")
            q.put({"event": "error", "detail": "Batch scan failed", "code": 500})
        finally:
            q.put(None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    def event_generator():
        while True:
            msg = q.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/scan", response_model=ScanResult)
async def scan(scan_filter: ScanFilter):
    try:
        return run_batch_analysis(scan_filter)
    except Exception:
        logger.exception("Batch scan failed")
        raise HTTPException(status_code=500, detail="Batch scan failed") from None


# ---------------------------------------------------------------------------
# v2: Raw SQL analysis (no statement_id)
# ---------------------------------------------------------------------------

@app.post("/api/analyze/sql", response_model=RawSQLResult)
async def analyze_sql(req: RawSQLRequest):
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL text is required")
    try:
        recs, tables = run_sql_analysis(req.sql)
        hs = compute_health_score(recs)
        return RawSQLResult(
            recommendations=recs,
            health_score=hs.score,
            tables_referenced=tables,
        )
    except Exception:
        logger.exception("Raw SQL analysis failed")
        raise HTTPException(status_code=500, detail="SQL analysis failed") from None


# ---------------------------------------------------------------------------
# v2: History & trending
# ---------------------------------------------------------------------------

@app.get("/api/history")
async def get_history(statement_id: str | None = None, limit: int = 100):
    storage = get_storage()
    if statement_id:
        return storage.get_history(statement_id)
    return storage.get_all_history(limit=limit)


@app.get("/api/trends")
async def get_trends(statement_id: str | None = None, limit: int = 200):
    storage = get_storage()
    if statement_id:
        return storage.get_trend(statement_id)
    return storage.get_global_trend(limit=limit)


# ---------------------------------------------------------------------------
# v2: Annotations
# ---------------------------------------------------------------------------

class AnnotationRequest(BaseModel):
    statement_id: str
    recommendation_title: str
    status: AnnotationStatus
    note: str | None = None


@app.post("/api/annotations", response_model=RecommendationAnnotation)
async def create_annotation(req: AnnotationRequest):
    storage = get_storage()
    annotation = RecommendationAnnotation(
        id=str(uuid.uuid4()),
        statement_id=req.statement_id,
        recommendation_title=req.recommendation_title,
        status=req.status,
        note=req.note,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    storage.save_annotation(annotation)
    return annotation


@app.get("/api/annotations/{statement_id}")
async def get_annotations(statement_id: str):
    storage = get_storage()
    return storage.get_annotations(statement_id)


@app.delete("/api/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str):
    storage = get_storage()
    deleted = storage.delete_annotation(annotation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# v2: Table health scanner
# ---------------------------------------------------------------------------

@app.post("/api/tables/scan", response_model=TableHealthResult)
async def scan_tables(req: TableHealthScanFilter):
    try:
        table_names = list_tables_in_schema(
            req.catalog, req.schema_name,
            table_name_pattern=req.table_name_pattern,
            max_results=req.max_results,
        )
        parsed = parse_query("SELECT 1")
        tables = analyze_tables(table_names, parsed)
        return TableHealthResult(
            tables=tables,
            total_scanned=len(tables),
            scanned_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        logger.exception("Table scan failed")
        raise HTTPException(status_code=500, detail="Table scan failed") from None


# ---------------------------------------------------------------------------
# v2: Warehouse fleet
# ---------------------------------------------------------------------------

@app.get("/api/warehouses", response_model=WarehouseFleetResult)
async def get_warehouses():
    try:
        raw_list = list_warehouses()
        warehouses = []
        for raw in raw_list:
            wid = raw.get("warehouse_id", "")
            if wid:
                try:
                    wh_info = analyze_warehouse(wid)
                    warehouses.append(wh_info)
                except Exception:
                    logger.warning("Failed to analyze warehouse %s", wid)
                    warehouses.append(WarehouseInfo(warehouse_id=wid, name=raw.get("name")))
        return WarehouseFleetResult(
            warehouses=warehouses,
            scanned_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        logger.exception("Warehouse fleet scan failed")
        raise HTTPException(status_code=500, detail="Warehouse fleet scan failed") from None


# ---------------------------------------------------------------------------
# v2: Export
# ---------------------------------------------------------------------------

@app.post("/api/export")
async def export_analysis(req: ExportRequest):
    _validate_statement_id(req.statement_id)
    analysis = _cache_get(req.statement_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found in cache. Re-analyze first.")

    hs = compute_health_score(analysis.recommendations)

    if req.format == "json":
        return analysis.model_dump(mode="json")

    if req.format == "html":
        html = _render_export_html(analysis, hs)
        return StreamingResponse(
            iter([html]),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=analysis_{req.statement_id[:8]}.html"},
        )

    md = _render_export_markdown(analysis, hs)
    return StreamingResponse(
        iter([md]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=analysis_{req.statement_id[:8]}.md"},
    )


def _render_export_markdown(analysis: AnalysisResult, hs: HealthScore) -> str:
    m = analysis.query_metrics
    lines = [
        f"# Query Analysis: {m.statement_id}",
        "",
        f"**Health Score:** {hs.score}/100",
        f"**Status:** {m.execution_status}",
        f"**Duration:** {m.total_duration_ms or 'N/A'} ms",
        "",
        "## SQL",
        "```sql",
        m.statement_text,
        "```",
        "",
        f"## Recommendations ({len(analysis.recommendations)})",
        "",
    ]
    for r in analysis.recommendations:
        lines.append(f"### [{r.severity.value.upper()}] {r.title} (impact: {r.impact}/10)")
        lines.append(f"{r.description}")
        if r.action:
            lines.append(f"\n**Action:** {r.action}")
        lines.append("")
    return "\n".join(lines)


def _render_export_html(analysis: AnalysisResult, hs: HealthScore) -> str:
    m = analysis.query_metrics
    recs_html = ""
    for r in analysis.recommendations:
        color = {"critical": "#dc2626", "warning": "#d97706", "info": "#2563eb"}.get(r.severity.value, "#666")
        recs_html += f"""
        <div style="border-left:3px solid {color};padding:12px;margin:8px 0;background:#fafafa;border-radius:4px">
            <strong>[{r.severity.value.upper()}]</strong> {r.title}
            <span style="float:right;color:{color}">Impact: {r.impact}/10</span>
            <p style="color:#555;margin:4px 0">{r.description}</p>
            {"<p><strong>Action:</strong> " + r.action + "</p>" if r.action else ""}
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Analysis: {m.statement_id[:8]}</title>
<style>body{{font-family:Inter,system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#333}}
pre{{background:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:6px;overflow-x:auto}}
h1{{border-bottom:2px solid #e5e7eb;padding-bottom:8px}}</style></head>
<body><h1>Query Analysis</h1>
<p><strong>Statement ID:</strong> {m.statement_id}</p>
<p><strong>Health Score:</strong> {hs.score}/100</p>
<p><strong>Duration:</strong> {m.total_duration_ms or 'N/A'} ms</p>
<h2>SQL</h2><pre>{m.statement_text}</pre>
<h2>Recommendations ({len(analysis.recommendations)})</h2>{recs_html}
</body></html>"""


# ---------------------------------------------------------------------------
# Static files (built React frontend)
# ---------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

assets_dir = os.path.join(static_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{full_path:path}")
async def serve_react(full_path: str):  # noqa: ARG001
    index_html = os.path.join(static_dir, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Please run 'npm run build' first.",
    )
