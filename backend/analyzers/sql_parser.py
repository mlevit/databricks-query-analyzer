from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

LARGE_IN_LIST_THRESHOLD = 50
DEEP_NESTING_THRESHOLD = 4
HIGH_GROUP_BY_COLUMNS = 5


@dataclass
class ParsedQuery:
    tables: list[str] = field(default_factory=list)
    joins: list[JoinInfo] = field(default_factory=list)
    has_select_star: bool = False
    has_order_by_in_subquery: bool = False
    has_cross_join: bool = False
    missing_where: bool = False
    filter_columns: list[str] = field(default_factory=list)
    join_columns: list[str] = field(default_factory=list)
    has_function_on_filter_column: bool = False
    has_function_on_join_key: bool = False
    has_limit: bool = False
    # Per-table filter column mapping: table_name -> [col1, col2, ...]
    table_filter_columns: dict[str, list[str]] = field(default_factory=dict)
    # New pattern flags
    has_union_without_all: bool = False
    has_not_in_subquery: bool = False
    has_leading_wildcard_like: bool = False
    has_distinct: bool = False
    has_correlated_subquery: bool = False
    has_unpartitioned_window: bool = False
    large_in_list_count: int = 0
    has_count_distinct: bool = False
    has_complex_or_filter: bool = False
    # Additional pattern flags
    has_scalar_subquery_in_select: bool = False
    has_distinct_with_joins: bool = False
    repeated_union_all_tables: list[str] = field(default_factory=list)
    max_nesting_depth: int = 0
    has_implicit_cast_in_predicate: bool = False
    has_or_different_columns: bool = False
    has_missing_join_predicate: bool = False
    has_order_by_without_limit: bool = False
    group_by_column_count: int = 0


@dataclass
class JoinInfo:
    join_type: str
    left_table: str | None = None
    right_table: str | None = None
    on_columns: list[str] = field(default_factory=list)


def parse_query(sql: str) -> ParsedQuery:
    result = ParsedQuery()
    try:
        parsed = sqlglot.parse(sql, error_level=sqlglot.ErrorLevel.IGNORE)
    except Exception:
        logger.warning("sqlglot failed to parse query, returning empty result")
        return result

    if not parsed:
        return result

    for statement in parsed:
        if statement is None:
            continue
        _extract_tables(statement, result)
        _check_select_star(statement, result)
        _extract_joins(statement, result)
        _check_where(statement, result)
        _extract_filters(statement, result)
        _check_order_in_subquery(statement, result)
        _check_limit(statement, result)
        _check_union_without_all(statement, result)
        _check_not_in_subquery(statement, result)
        _check_leading_wildcard_like(statement, result)
        _check_distinct(statement, result)
        _check_correlated_subquery(statement, result)
        _check_unpartitioned_window(statement, result)
        _check_large_in_list(statement, result)
        _check_count_distinct(statement, result)
        _check_complex_or_filter(statement, result)
        _check_scalar_subquery_in_select(statement, result)
        _check_distinct_with_joins(statement, result)
        _check_repeated_table_in_union_all(statement, result)
        _check_deep_nesting(statement, result)
        _check_implicit_cast_in_predicate(statement, result)
        _check_or_different_columns(statement, result)
        _check_missing_join_predicate(statement, result)
        _check_order_by_without_limit(statement, result)
        _check_group_by_columns(statement, result)

    result.tables = list(dict.fromkeys(result.tables))
    return result


def _extract_tables(node: exp.Expression, result: ParsedQuery) -> None:
    virtual_names: set[str] = set()

    for cte in node.find_all(exp.CTE):
        alias = cte.args.get("alias")
        if alias and isinstance(alias, exp.TableAlias):
            virtual_names.add(alias.name.lower())
        elif alias:
            virtual_names.add(str(alias).lower())

    for subq in node.find_all(exp.Subquery):
        alias = subq.args.get("alias")
        if alias and isinstance(alias, exp.TableAlias):
            virtual_names.add(alias.name.lower())
        elif alias:
            virtual_names.add(str(alias).lower())

    for table in node.find_all(exp.Table):
        parts = []
        if table.catalog:
            parts.append(table.catalog)
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        if not parts:
            continue

        full_name = ".".join(parts)

        if full_name.lower() in virtual_names:
            continue

        result.tables.append(full_name)


def _check_select_star(node: exp.Expression, result: ParsedQuery) -> None:
    for select in node.find_all(exp.Select):
        for expr in select.expressions:
            if isinstance(expr, exp.Star):
                result.has_select_star = True
                return


def _extract_joins(node: exp.Expression, result: ParsedQuery) -> None:
    for join in node.find_all(exp.Join):
        join_type = join.side or ""
        kind = join.kind or ""
        full_type = f"{join_type} {kind}".strip().upper() or "INNER"

        if kind and kind.upper() == "CROSS":
            result.has_cross_join = True

        right_table = None
        table_node = join.find(exp.Table)
        if table_node:
            parts = []
            if table_node.catalog:
                parts.append(table_node.catalog)
            if table_node.db:
                parts.append(table_node.db)
            if table_node.name:
                parts.append(table_node.name)
            right_table = ".".join(parts) if parts else None

        on_cols: list[str] = []
        on_clause = join.args.get("on")
        if on_clause:
            for col in on_clause.find_all(exp.Column):
                on_cols.append(col.name)
                result.join_columns.append(col.name)
                if _is_wrapped_in_function(col):
                    result.has_function_on_join_key = True

        result.joins.append(JoinInfo(
            join_type=full_type,
            right_table=right_table,
            on_columns=on_cols,
        ))


def _check_where(node: exp.Expression, result: ParsedQuery) -> None:
    """Check if the outermost query lacks a WHERE clause."""
    top_select = node.find(exp.Select)
    if not top_select:
        return
    parent_query = top_select.parent
    if parent_query and not parent_query.find(exp.Where):
        result.missing_where = True


def _extract_filters(node: exp.Expression, result: ParsedQuery) -> None:
    """Extract filter columns and build per-table filter column mapping."""
    table_alias_map = _build_table_alias_map(node)

    for where in node.find_all(exp.Where):
        for col in where.find_all(exp.Column):
            col_name = col.name
            result.filter_columns.append(col_name)
            if _is_wrapped_in_function(col):
                result.has_function_on_filter_column = True

            table_ref = col.table
            if table_ref:
                resolved = table_alias_map.get(table_ref.lower(), table_ref)
                result.table_filter_columns.setdefault(resolved, []).append(col_name)


def _build_table_alias_map(node: exp.Expression) -> dict[str, str]:
    """Map table aliases to their full qualified names."""
    alias_map: dict[str, str] = {}
    for table in node.find_all(exp.Table):
        parts = []
        if table.catalog:
            parts.append(table.catalog)
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        if not parts:
            continue
        full_name = ".".join(parts)
        alias = table.alias
        if alias:
            alias_map[alias.lower()] = full_name
    return alias_map


def _check_order_in_subquery(node: exp.Expression, result: ParsedQuery) -> None:
    for subquery in node.find_all(exp.Subquery):
        if subquery.find(exp.Order):
            result.has_order_by_in_subquery = True
            return


def _check_limit(node: exp.Expression, result: ParsedQuery) -> None:
    if node.find(exp.Limit):
        result.has_limit = True


# ---------------------------------------------------------------------------
# A1: UNION without ALL
# ---------------------------------------------------------------------------
def _check_union_without_all(node: exp.Expression, result: ParsedQuery) -> None:
    for union in node.find_all(exp.Union):
        if not union.args.get("distinct") is False:
            if not isinstance(union, exp.Intersect) and not isinstance(union, exp.Except):
                result.has_union_without_all = True
                return


# ---------------------------------------------------------------------------
# A2: NOT IN subquery
# ---------------------------------------------------------------------------
def _check_not_in_subquery(node: exp.Expression, result: ParsedQuery) -> None:
    for not_node in node.find_all(exp.Not):
        child = not_node.this
        if isinstance(child, exp.In):
            expressions = child.args.get("expressions", [])
            query = child.args.get("query")
            if query or any(isinstance(e, exp.Subquery) for e in expressions):
                result.has_not_in_subquery = True
                return


# ---------------------------------------------------------------------------
# A3: LIKE with leading wildcard
# ---------------------------------------------------------------------------
def _check_leading_wildcard_like(node: exp.Expression, result: ParsedQuery) -> None:
    for like in node.find_all(exp.Like):
        pattern = like.expression
        if isinstance(pattern, exp.Literal) and pattern.is_string:
            val = pattern.this
            if isinstance(val, str) and val.startswith("%"):
                result.has_leading_wildcard_like = True
                return


# ---------------------------------------------------------------------------
# A4: SELECT DISTINCT (outer queries only, not EXISTS subqueries)
# ---------------------------------------------------------------------------
def _check_distinct(node: exp.Expression, result: ParsedQuery) -> None:
    for select in node.find_all(exp.Select):
        if not select.args.get("distinct"):
            continue
        parent = select.parent
        if isinstance(parent, exp.Subquery):
            grandparent = parent.parent
            if isinstance(grandparent, exp.Exists):
                continue
        result.has_distinct = True
        return


# ---------------------------------------------------------------------------
# A5: Correlated subqueries
# ---------------------------------------------------------------------------
def _check_correlated_subquery(node: exp.Expression, result: ParsedQuery) -> None:
    outer_tables = _collect_scope_tables(node)

    for subquery in node.find_all(exp.Subquery):
        if isinstance(subquery.parent, exp.Exists):
            continue
        inner_tables = _collect_scope_tables(subquery)
        for col in subquery.find_all(exp.Column):
            table_ref = col.table
            if table_ref and table_ref.lower() in outer_tables and table_ref.lower() not in inner_tables:
                result.has_correlated_subquery = True
                return


def _collect_scope_tables(node: exp.Expression) -> set[str]:
    """Collect table names and aliases directly referenced in this scope."""
    names: set[str] = set()
    for table in node.find_all(exp.Table):
        if table.name:
            names.add(table.name.lower())
        if table.alias:
            names.add(table.alias.lower())
    return names


# ---------------------------------------------------------------------------
# A6: Window functions without PARTITION BY
# ---------------------------------------------------------------------------
def _check_unpartitioned_window(node: exp.Expression, result: ParsedQuery) -> None:
    for window in node.find_all(exp.Window):
        partition_by = window.args.get("partition_by")
        if not partition_by:
            result.has_unpartitioned_window = True
            return


# ---------------------------------------------------------------------------
# A7: Large IN lists
# ---------------------------------------------------------------------------
def _check_large_in_list(node: exp.Expression, result: ParsedQuery) -> None:
    for in_node in node.find_all(exp.In):
        expressions = in_node.args.get("expressions", [])
        if len(expressions) >= LARGE_IN_LIST_THRESHOLD:
            result.large_in_list_count += 1


# ---------------------------------------------------------------------------
# A8: COUNT(DISTINCT ...)
# ---------------------------------------------------------------------------
def _check_count_distinct(node: exp.Expression, result: ParsedQuery) -> None:
    for count in node.find_all(exp.Count):
        if count.args.get("distinct"):
            result.has_count_distinct = True
            return


# ---------------------------------------------------------------------------
# A9: Complex OR filters (3+ branches)
# ---------------------------------------------------------------------------
def _check_complex_or_filter(node: exp.Expression, result: ParsedQuery) -> None:
    for where in node.find_all(exp.Where):
        or_count = _count_or_branches(where.this)
        if or_count >= 3:
            result.has_complex_or_filter = True
            return


def _count_or_branches(expr: exp.Expression) -> int:
    """Count the number of OR branches in a boolean expression."""
    if isinstance(expr, exp.Or):
        return _count_or_branches(expr.left) + _count_or_branches(expr.right)
    return 1


# ---------------------------------------------------------------------------
# A10: Scalar subqueries in SELECT (N+1 pattern)
# ---------------------------------------------------------------------------
def _check_scalar_subquery_in_select(node: exp.Expression, result: ParsedQuery) -> None:
    for select in node.find_all(exp.Select):
        for expr in select.expressions:
            target = expr.this if isinstance(expr, exp.Alias) else expr
            if isinstance(target, exp.Subquery):
                result.has_scalar_subquery_in_select = True
                return


# ---------------------------------------------------------------------------
# A11: DISTINCT used alongside JOINs (fan-out mask)
# ---------------------------------------------------------------------------
def _check_distinct_with_joins(node: exp.Expression, result: ParsedQuery) -> None:
    for select in node.find_all(exp.Select):
        if not select.args.get("distinct"):
            continue
        parent = select.parent
        if isinstance(parent, exp.Subquery):
            grandparent = parent.parent
            if isinstance(grandparent, exp.Exists):
                continue
        scope = select.parent if select.parent else select
        if scope.find(exp.Join):
            result.has_distinct_with_joins = True
            return


# ---------------------------------------------------------------------------
# A12: Same table scanned multiple times in UNION ALL branches
# ---------------------------------------------------------------------------
def _check_repeated_table_in_union_all(node: exp.Expression, result: ParsedQuery) -> None:
    for union in node.find_all(exp.Union):
        if isinstance(union, (exp.Intersect, exp.Except)):
            continue
        if union.args.get("distinct") is not False:
            continue

        branches: list[exp.Expression] = []
        _collect_union_all_branches(union, branches)
        if len(branches) < 2:
            continue

        table_counts: dict[str, int] = {}
        for branch in branches:
            branch_tables: set[str] = set()
            for table in branch.find_all(exp.Table):
                name = table.name.lower() if table.name else ""
                if name:
                    branch_tables.add(name)
            for t in branch_tables:
                table_counts[t] = table_counts.get(t, 0) + 1

        for table_name, count in table_counts.items():
            if count > 1:
                result.repeated_union_all_tables.append(table_name)

    result.repeated_union_all_tables = list(dict.fromkeys(result.repeated_union_all_tables))


def _collect_union_all_branches(
    node: exp.Expression, branches: list[exp.Expression],
) -> None:
    """Recursively collect leaf SELECT branches of a UNION ALL chain."""
    if isinstance(node, exp.Union) and node.args.get("distinct") is False:
        _collect_union_all_branches(node.left, branches)
        _collect_union_all_branches(node.right, branches)
    else:
        branches.append(node)


# ---------------------------------------------------------------------------
# A13: Deeply nested subqueries / CTEs
# ---------------------------------------------------------------------------
def _check_deep_nesting(node: exp.Expression, result: ParsedQuery) -> None:
    depth = _measure_subquery_depth(node, 0)
    result.max_nesting_depth = max(result.max_nesting_depth, depth)


def _measure_subquery_depth(node: exp.Expression, current: int) -> int:
    max_depth = current
    for child in node.find_all(exp.Subquery):
        if child is node:
            continue
        max_depth = max(max_depth, _measure_subquery_depth(child, current + 1))
    return max_depth


# ---------------------------------------------------------------------------
# A14: CAST / TRY_CAST wrapping a column in WHERE or JOIN ON
# ---------------------------------------------------------------------------
def _check_implicit_cast_in_predicate(node: exp.Expression, result: ParsedQuery) -> None:
    for cast_node in node.find_all(exp.Cast):
        if not isinstance(cast_node.this, exp.Column):
            continue
        parent = cast_node.parent
        while parent:
            if isinstance(parent, (exp.Where, exp.Join)):
                result.has_implicit_cast_in_predicate = True
                return
            if isinstance(parent, (exp.Select,)):
                break
            parent = parent.parent


# ---------------------------------------------------------------------------
# A15: OR branches referencing different columns in WHERE
# ---------------------------------------------------------------------------
def _check_or_different_columns(node: exp.Expression, result: ParsedQuery) -> None:
    for where in node.find_all(exp.Where):
        if _or_spans_different_columns(where.this):
            result.has_or_different_columns = True
            return


def _or_spans_different_columns(expr: exp.Expression) -> bool:
    """Return True if an OR expression has branches referencing different columns."""
    if not isinstance(expr, exp.Or):
        return False
    branch_columns: list[set[str]] = []
    _collect_or_branch_columns(expr, branch_columns)
    if len(branch_columns) < 2:
        return False
    first = branch_columns[0]
    return any(cols != first for cols in branch_columns[1:])


def _collect_or_branch_columns(
    expr: exp.Expression, result: list[set[str]],
) -> None:
    if isinstance(expr, exp.Or):
        _collect_or_branch_columns(expr.left, result)
        _collect_or_branch_columns(expr.right, result)
    else:
        cols = {col.name.lower() for col in expr.find_all(exp.Column)}
        result.append(cols)


# ---------------------------------------------------------------------------
# A16: JOIN without ON clause (not CROSS JOIN) — silent cartesian
# ---------------------------------------------------------------------------
def _check_missing_join_predicate(node: exp.Expression, result: ParsedQuery) -> None:
    for join in node.find_all(exp.Join):
        kind = (join.kind or "").upper()
        if kind == "CROSS":
            continue
        on_clause = join.args.get("on")
        using_clause = join.args.get("using")
        if not on_clause and not using_clause:
            result.has_missing_join_predicate = True
            return


# ---------------------------------------------------------------------------
# A17: ORDER BY without LIMIT at the outermost query level
# ---------------------------------------------------------------------------
def _check_order_by_without_limit(node: exp.Expression, result: ParsedQuery) -> None:
    order = node.find(exp.Order)
    if not order:
        return
    parent = order.parent
    while parent:
        if isinstance(parent, exp.Subquery):
            return
        parent = parent.parent
    if not node.find(exp.Limit):
        result.has_order_by_without_limit = True


# ---------------------------------------------------------------------------
# A18: GROUP BY with many columns (high-cardinality heuristic)
# ---------------------------------------------------------------------------
def _check_group_by_columns(node: exp.Expression, result: ParsedQuery) -> None:
    for group in node.find_all(exp.Group):
        col_count = len(list(group.find_all(exp.Column)))
        result.group_by_column_count = max(result.group_by_column_count, col_count)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_wrapped_in_function(col: exp.Column) -> bool:
    parent = col.parent
    while parent:
        if isinstance(parent, (exp.Anonymous, exp.Func)):
            return True
        if isinstance(parent, (exp.Where, exp.Join, exp.Select)):
            break
        parent = parent.parent
    return False
