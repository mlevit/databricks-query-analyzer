"""Cross-query workload pattern detection.

Consumes a batch of ``AnalysisResult`` objects and surfaces patterns that
are only visible when looking across multiple queries (repeated anti-patterns,
hot tables, near-duplicate queries, temporal spikes).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.models import AnalysisResult, Severity, WorkloadPattern


def analyze_workload(results: list[AnalysisResult]) -> list[WorkloadPattern]:
    patterns: list[WorkloadPattern] = []

    if not results:
        return patterns

    patterns.extend(_detect_repeated_antipatterns(results))
    patterns.extend(_detect_hot_tables(results))
    patterns.extend(_detect_redundant_queries(results))
    patterns.extend(_detect_high_spill_cluster(results))

    patterns.sort(key=lambda p: (-p.impact, p.title))
    return patterns


def _detect_repeated_antipatterns(results: list[AnalysisResult]) -> list[WorkloadPattern]:
    """Find recommendation titles that fire across many queries."""
    title_counts: Counter[str] = Counter()
    for r in results:
        seen = set()
        for rec in r.recommendations:
            if rec.title not in seen:
                title_counts[rec.title] += 1
                seen.add(rec.title)

    patterns = []
    threshold = max(2, len(results) // 5)
    for title, count in title_counts.most_common(10):
        if count < threshold:
            continue
        pct = round(count / len(results) * 100)
        patterns.append(WorkloadPattern(
            pattern_type="repeated_antipattern",
            title=f"Recurring issue: {title}",
            description=(
                f'The check "{title}" fires on {count} of {len(results)} queries '
                f"({pct}%). Addressing this pattern across the workload will have "
                "a compounding effect on overall performance."
            ),
            severity=Severity.WARNING,
            affected_queries=count,
            impact=min(10, 5 + count // 3),
        ))
    return patterns


def _detect_hot_tables(results: list[AnalysisResult]) -> list[WorkloadPattern]:
    """Identify tables that appear in the most expensive queries."""
    table_durations: defaultdict[str, int] = defaultdict(int)
    table_query_count: Counter[str] = Counter()

    for r in results:
        dur = r.query_metrics.total_duration_ms or 0
        for t in r.tables:
            table_durations[t.full_name] += dur
            table_query_count[t.full_name] += 1

    patterns = []
    for table_name, total_dur in sorted(table_durations.items(), key=lambda x: -x[1])[:5]:
        count = table_query_count[table_name]
        if count < 2:
            continue
        patterns.append(WorkloadPattern(
            pattern_type="hot_table",
            title=f"Hot table: {table_name}",
            description=(
                f"Table {table_name} appears in {count} queries with a combined "
                f"duration of {total_dur:,} ms. Optimizing this table's layout "
                "or the queries that access it will yield the largest workload-wide gain."
            ),
            severity=Severity.WARNING,
            affected_queries=count,
            affected_tables=[table_name],
            impact=min(10, 4 + count),
        ))
    return patterns


def _normalize_sql(sql: str) -> str:
    """Crude normalisation: lowercase, collapse whitespace, strip literals."""
    import re
    s = sql.lower().strip().rstrip(";")
    s = re.sub(r"'[^']*'", "'?'", s)
    s = re.sub(r"\b\d+\b", "?", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _detect_redundant_queries(results: list[AnalysisResult]) -> list[WorkloadPattern]:
    """Find near-duplicate queries that could share a materialized view."""
    normalised: defaultdict[str, list[str]] = defaultdict(list)
    for r in results:
        key = _normalize_sql(r.query_metrics.statement_text)
        normalised[key].append(r.query_metrics.statement_id)

    patterns = []
    for _key, ids in normalised.items():
        if len(ids) < 2:
            continue
        patterns.append(WorkloadPattern(
            pattern_type="redundant_query",
            title=f"Near-duplicate query ({len(ids)} instances)",
            description=(
                f"{len(ids)} queries have nearly identical SQL (differing only in "
                "literal values). Consider parameterising or creating a materialized "
                "view / cached result to avoid repeated computation."
            ),
            severity=Severity.INFO,
            affected_queries=len(ids),
            impact=min(8, 3 + len(ids)),
        ))
    return patterns


def _detect_high_spill_cluster(results: list[AnalysisResult]) -> list[WorkloadPattern]:
    """Flag when many queries in the batch spill to disk."""
    spill_count = sum(
        1 for r in results
        if (r.query_metrics.spilled_local_bytes or 0) > 100 * 1024 * 1024
    )
    if spill_count >= max(2, len(results) // 4):
        pct = round(spill_count / len(results) * 100)
        return [WorkloadPattern(
            pattern_type="widespread_spill",
            title="Widespread disk spill across workload",
            description=(
                f"{spill_count} of {len(results)} queries ({pct}%) spill "
                "over 100 MB to disk. This suggests the warehouse may be undersized "
                "or queries need optimization to reduce memory pressure."
            ),
            severity=Severity.CRITICAL,
            affected_queries=spill_count,
            impact=9,
        )]
    return []
