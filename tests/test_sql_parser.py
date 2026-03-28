"""Tests for backend.analyzers.sql_parser."""

from backend.analyzers.sql_parser import parse_query


class TestTableExtraction:
    def test_simple_table(self):
        result = parse_query("SELECT * FROM my_catalog.my_schema.my_table")
        assert "my_catalog.my_schema.my_table" in result.tables

    def test_cte_excluded(self):
        sql = """
        WITH cte AS (SELECT 1 AS x)
        SELECT * FROM cte
        """
        result = parse_query(sql)
        assert "cte" not in [t.lower() for t in result.tables]

    def test_subquery_alias_excluded(self):
        sql = "SELECT * FROM (SELECT 1 AS x) sub"
        result = parse_query(sql)
        assert "sub" not in [t.lower() for t in result.tables]

    def test_multiple_tables(self):
        sql = "SELECT * FROM a.b.c JOIN a.b.d ON c.id = d.id"
        result = parse_query(sql)
        assert "a.b.c" in result.tables
        assert "a.b.d" in result.tables

    def test_deduplicate_tables(self):
        sql = "SELECT * FROM t WHERE id IN (SELECT id FROM t)"
        result = parse_query(sql)
        assert result.tables.count("t") == 1


class TestSelectStar:
    def test_detects_select_star(self):
        result = parse_query("SELECT * FROM t")
        assert result.has_select_star is True

    def test_no_select_star(self):
        result = parse_query("SELECT id, name FROM t")
        assert result.has_select_star is False


class TestJoinExtraction:
    def test_cross_join(self):
        result = parse_query("SELECT * FROM a CROSS JOIN b")
        assert result.has_cross_join is True
        assert len(result.joins) == 1

    def test_inner_join(self):
        result = parse_query("SELECT * FROM a JOIN b ON a.id = b.id")
        assert len(result.joins) == 1
        assert "INNER" in result.joins[0].join_type or result.joins[0].join_type == ""

    def test_join_columns_extracted(self):
        result = parse_query("SELECT * FROM a JOIN b ON a.id = b.id")
        assert "id" in result.join_columns


class TestWhereClause:
    def test_missing_where(self):
        result = parse_query("SELECT * FROM t")
        assert result.missing_where is True

    def test_has_where(self):
        result = parse_query("SELECT * FROM t WHERE id = 1")
        assert result.missing_where is False

    def test_filter_columns_extracted(self):
        result = parse_query("SELECT * FROM t WHERE status = 'active' AND created_at > '2024-01-01'")
        assert "status" in result.filter_columns
        assert "created_at" in result.filter_columns


class TestFunctionOnFilterColumn:
    def test_function_on_filter(self):
        result = parse_query("SELECT * FROM t WHERE UPPER(name) = 'TEST'")
        assert result.has_function_on_filter_column is True

    def test_no_function_on_filter(self):
        result = parse_query("SELECT * FROM t WHERE name = 'test'")
        assert result.has_function_on_filter_column is False


class TestLimit:
    def test_has_limit(self):
        result = parse_query("SELECT * FROM t LIMIT 10")
        assert result.has_limit is True

    def test_no_limit(self):
        result = parse_query("SELECT * FROM t")
        assert result.has_limit is False


class TestUnionWithoutAll:
    def test_union_without_all(self):
        result = parse_query("SELECT id FROM a UNION SELECT id FROM b")
        assert result.has_union_without_all is True

    def test_union_all(self):
        result = parse_query("SELECT id FROM a UNION ALL SELECT id FROM b")
        assert result.has_union_without_all is False


class TestNotInSubquery:
    def test_not_in_subquery(self):
        result = parse_query("SELECT * FROM t WHERE id NOT IN (SELECT id FROM s)")
        assert result.has_not_in_subquery is True

    def test_regular_not_in(self):
        result = parse_query("SELECT * FROM t WHERE id NOT IN (1, 2, 3)")
        assert result.has_not_in_subquery is False


class TestLeadingWildcardLike:
    def test_leading_wildcard(self):
        result = parse_query("SELECT * FROM t WHERE name LIKE '%test'")
        assert result.has_leading_wildcard_like is True

    def test_trailing_wildcard(self):
        result = parse_query("SELECT * FROM t WHERE name LIKE 'test%'")
        assert result.has_leading_wildcard_like is False


class TestDistinct:
    def test_has_distinct(self):
        result = parse_query("SELECT DISTINCT id FROM t")
        assert result.has_distinct is True

    def test_no_distinct(self):
        result = parse_query("SELECT id FROM t")
        assert result.has_distinct is False


class TestUnpartitionedWindow:
    def test_window_without_partition(self):
        result = parse_query("SELECT ROW_NUMBER() OVER (ORDER BY id) FROM t")
        assert result.has_unpartitioned_window is True

    def test_window_with_partition(self):
        result = parse_query("SELECT ROW_NUMBER() OVER (PARTITION BY cat ORDER BY id) FROM t")
        assert result.has_unpartitioned_window is False


class TestLargeInList:
    def test_large_in_list(self):
        values = ", ".join(str(i) for i in range(60))
        result = parse_query(f"SELECT * FROM t WHERE id IN ({values})")
        assert result.large_in_list_count >= 1

    def test_small_in_list(self):
        result = parse_query("SELECT * FROM t WHERE id IN (1, 2, 3)")
        assert result.large_in_list_count == 0


class TestCountDistinct:
    def test_count_distinct(self):
        result = parse_query("SELECT COUNT(DISTINCT user_id) FROM t")
        assert result.has_count_distinct is True

    def test_regular_count(self):
        result = parse_query("SELECT COUNT(*) FROM t")
        assert result.has_count_distinct is False


class TestComplexOrFilter:
    def test_complex_or(self):
        result = parse_query("SELECT * FROM t WHERE a = 1 OR b = 2 OR c = 3")
        assert result.has_complex_or_filter is True

    def test_simple_or(self):
        result = parse_query("SELECT * FROM t WHERE a = 1 OR b = 2")
        assert result.has_complex_or_filter is False


class TestOrderInSubquery:
    def test_order_in_subquery(self):
        result = parse_query("SELECT * FROM (SELECT id FROM t ORDER BY id) sub")
        assert result.has_order_by_in_subquery is True

    def test_order_at_top_level(self):
        result = parse_query("SELECT id FROM t ORDER BY id")
        assert result.has_order_by_in_subquery is False


class TestScalarSubqueryInSelect:
    def test_scalar_subquery_detected(self):
        sql = """
        SELECT
            c.name,
            (SELECT MAX(amount) FROM orders o WHERE o.cid = c.id) AS max_amt
        FROM customers c
        """
        result = parse_query(sql)
        assert result.has_scalar_subquery_in_select is True

    def test_no_subquery_in_select(self):
        result = parse_query("SELECT id, name FROM t")
        assert result.has_scalar_subquery_in_select is False

    def test_subquery_in_where_not_flagged(self):
        result = parse_query("SELECT id FROM t WHERE id IN (SELECT id FROM s)")
        assert result.has_scalar_subquery_in_select is False


class TestDistinctWithJoins:
    def test_distinct_with_join(self):
        sql = "SELECT DISTINCT a.id FROM a JOIN b ON a.id = b.id"
        result = parse_query(sql)
        assert result.has_distinct_with_joins is True

    def test_distinct_without_join(self):
        result = parse_query("SELECT DISTINCT id FROM t")
        assert result.has_distinct_with_joins is False

    def test_no_distinct_with_join(self):
        result = parse_query("SELECT a.id FROM a JOIN b ON a.id = b.id")
        assert result.has_distinct_with_joins is False


class TestRepeatedTableInUnionAll:
    def test_same_table_in_union_all(self):
        sql = """
        SELECT id FROM orders WHERE status = 'A'
        UNION ALL
        SELECT id FROM orders WHERE status = 'B'
        """
        result = parse_query(sql)
        assert "orders" in result.repeated_union_all_tables

    def test_different_tables_in_union_all(self):
        sql = """
        SELECT id FROM orders WHERE status = 'A'
        UNION ALL
        SELECT id FROM customers WHERE active = 1
        """
        result = parse_query(sql)
        assert result.repeated_union_all_tables == []

    def test_union_distinct_not_flagged(self):
        sql = """
        SELECT id FROM orders WHERE status = 'A'
        UNION
        SELECT id FROM orders WHERE status = 'B'
        """
        result = parse_query(sql)
        assert result.repeated_union_all_tables == []


class TestDeepNesting:
    def test_deep_nesting(self):
        sql = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT id FROM t
                    ) d
                ) c
            ) b
        ) a
        """
        result = parse_query(sql)
        assert result.max_nesting_depth >= 4

    def test_shallow_nesting(self):
        result = parse_query("SELECT * FROM (SELECT id FROM t) sub")
        assert result.max_nesting_depth < 4


class TestImplicitCastInPredicate:
    def test_cast_in_where(self):
        result = parse_query("SELECT * FROM t WHERE CAST(id AS STRING) = '123'")
        assert result.has_implicit_cast_in_predicate is True

    def test_no_cast_in_where(self):
        result = parse_query("SELECT * FROM t WHERE id = 123")
        assert result.has_implicit_cast_in_predicate is False

    def test_cast_in_select_not_flagged(self):
        result = parse_query("SELECT CAST(id AS STRING) FROM t WHERE id = 1")
        assert result.has_implicit_cast_in_predicate is False


class TestOrDifferentColumns:
    def test_or_different_columns(self):
        result = parse_query("SELECT * FROM t WHERE a = 1 OR b = 2")
        assert result.has_or_different_columns is True

    def test_or_same_column(self):
        result = parse_query("SELECT * FROM t WHERE a = 1 OR a = 2")
        assert result.has_or_different_columns is False

    def test_no_or(self):
        result = parse_query("SELECT * FROM t WHERE a = 1 AND b = 2")
        assert result.has_or_different_columns is False


class TestMissingJoinPredicate:
    def test_join_without_on(self):
        result = parse_query("SELECT * FROM a JOIN b")
        assert result.has_missing_join_predicate is True

    def test_join_with_on(self):
        result = parse_query("SELECT * FROM a JOIN b ON a.id = b.id")
        assert result.has_missing_join_predicate is False

    def test_cross_join_not_flagged(self):
        result = parse_query("SELECT * FROM a CROSS JOIN b")
        assert result.has_missing_join_predicate is False

    def test_join_with_using(self):
        result = parse_query("SELECT * FROM a JOIN b USING (id)")
        assert result.has_missing_join_predicate is False


class TestOrderByWithoutLimit:
    def test_order_by_no_limit(self):
        result = parse_query("SELECT id FROM t ORDER BY id")
        assert result.has_order_by_without_limit is True

    def test_order_by_with_limit(self):
        result = parse_query("SELECT id FROM t ORDER BY id LIMIT 10")
        assert result.has_order_by_without_limit is False

    def test_no_order_by(self):
        result = parse_query("SELECT id FROM t")
        assert result.has_order_by_without_limit is False


class TestGroupByManyColumns:
    def test_many_group_by_columns(self):
        result = parse_query(
            "SELECT a, b, c, d, e, COUNT(*) FROM t GROUP BY a, b, c, d, e"
        )
        assert result.group_by_column_count >= 5

    def test_few_group_by_columns(self):
        result = parse_query("SELECT a, COUNT(*) FROM t GROUP BY a")
        assert result.group_by_column_count < 5


class TestHavingWithoutAgg:
    def test_having_without_agg(self):
        sql = "SELECT dept, COUNT(*) FROM t GROUP BY dept HAVING dept = 'Sales'"
        result = parse_query(sql)
        assert result.has_having_without_agg is True

    def test_having_with_agg(self):
        sql = "SELECT dept, COUNT(*) AS cnt FROM t GROUP BY dept HAVING COUNT(*) > 5"
        result = parse_query(sql)
        assert result.has_having_without_agg is False

    def test_no_having(self):
        result = parse_query("SELECT dept, COUNT(*) FROM t GROUP BY dept")
        assert result.has_having_without_agg is False


class TestDeepPaginationOffset:
    def test_large_offset(self):
        result = parse_query("SELECT * FROM t ORDER BY id LIMIT 20 OFFSET 5000")
        assert result.has_deep_pagination_offset is True

    def test_small_offset(self):
        result = parse_query("SELECT * FROM t ORDER BY id LIMIT 20 OFFSET 10")
        assert result.has_deep_pagination_offset is False

    def test_no_offset(self):
        result = parse_query("SELECT * FROM t ORDER BY id LIMIT 20")
        assert result.has_deep_pagination_offset is False


class TestExactPercentile:
    def test_percentile_cont(self):
        sql = "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary) FROM t"
        result = parse_query(sql)
        assert result.has_exact_percentile is True

    def test_no_percentile(self):
        result = parse_query("SELECT AVG(salary) FROM t")
        assert result.has_exact_percentile is False


class TestNonEquiJoin:
    def test_range_join(self):
        sql = "SELECT * FROM a JOIN b ON a.ts > b.start_ts AND a.ts < b.end_ts"
        result = parse_query(sql)
        assert result.has_non_equi_join is False  # has both > and <, but no EQ

    def test_pure_range_join(self):
        sql = "SELECT * FROM a JOIN b ON a.val > b.val"
        result = parse_query(sql)
        assert result.has_non_equi_join is True

    def test_equi_join(self):
        result = parse_query("SELECT * FROM a JOIN b ON a.id = b.id")
        assert result.has_non_equi_join is False


class TestCountStarForExistence:
    def test_count_star_single_column(self):
        result = parse_query("SELECT COUNT(*) FROM t WHERE status = 'active'")
        assert result.has_count_star_for_existence is True

    def test_count_star_with_group_by(self):
        result = parse_query(
            "SELECT dept, COUNT(*) FROM t GROUP BY dept"
        )
        assert result.has_count_star_for_existence is False

    def test_count_column(self):
        result = parse_query("SELECT COUNT(id) FROM t")
        assert result.has_count_star_for_existence is False


class TestPossibleUdf:
    def test_udf_prefix(self):
        sql = "SELECT udf_compute_tax(amount) FROM orders"
        result = parse_query(sql)
        assert result.has_possible_udf is True

    def test_dotted_udf(self):
        sql = "SELECT my_catalog.my_schema.my_func(col) FROM t"
        result = parse_query(sql)
        assert result.has_possible_udf is True

    def test_builtin_function(self):
        result = parse_query("SELECT UPPER(name) FROM t")
        assert result.has_possible_udf is False


class TestStringJsonParsing:
    def test_get_json_object(self):
        sql = "SELECT get_json_object(payload, '$.name') FROM events"
        result = parse_query(sql)
        assert result.has_string_json_parsing is True

    def test_from_json(self):
        sql = "SELECT from_json(data, 'struct<name:string>') FROM events"
        result = parse_query(sql)
        assert result.has_string_json_parsing is True

    def test_json_tuple(self):
        sql = "SELECT json_tuple(payload, 'a', 'b') FROM events"
        result = parse_query(sql)
        assert result.has_string_json_parsing is True

    def test_no_json_parsing(self):
        result = parse_query("SELECT name, age FROM users")
        assert result.has_string_json_parsing is False

    def test_regexp_extract_json(self):
        sql = """SELECT regexp_extract(col, '"name":"([^"]*)"', 1) FROM t"""
        result = parse_query(sql)
        assert result.has_string_json_parsing is True


class TestWindowPartitionColumns:
    def test_extracts_partition_columns(self):
        sql = "SELECT ROW_NUMBER() OVER (PARTITION BY dept ORDER BY id) FROM t"
        result = parse_query(sql)
        assert "dept" in result.window_partition_columns

    def test_no_partition(self):
        sql = "SELECT ROW_NUMBER() OVER (ORDER BY id) FROM t"
        result = parse_query(sql)
        assert result.window_partition_columns == []


class TestSnippets:
    def test_implicit_cast_snippet(self):
        result = parse_query("SELECT * FROM t WHERE CAST(id AS STRING) = '123'")
        assert result.has_implicit_cast_in_predicate is True
        snippets = result.snippets.get("has_implicit_cast_in_predicate", [])
        assert len(snippets) == 1
        assert "CAST" in snippets[0].upper()
        assert "id" in snippets[0].lower()

    def test_leading_wildcard_like_snippet(self):
        result = parse_query("SELECT * FROM t WHERE name LIKE '%test'")
        snippets = result.snippets.get("has_leading_wildcard_like", [])
        assert len(snippets) == 1
        assert "%test" in snippets[0]

    def test_function_on_filter_column_snippet(self):
        result = parse_query("SELECT * FROM t WHERE UPPER(name) = 'TEST'")
        snippets = result.snippets.get("has_function_on_filter_column", [])
        assert len(snippets) >= 1
        assert "UPPER" in snippets[0].upper()

    def test_not_in_subquery_snippet(self):
        result = parse_query("SELECT * FROM t WHERE id NOT IN (SELECT id FROM s)")
        snippets = result.snippets.get("has_not_in_subquery", [])
        assert len(snippets) == 1
        assert "NOT" in snippets[0].upper()

    def test_count_distinct_snippet(self):
        result = parse_query("SELECT COUNT(DISTINCT user_id) FROM t")
        snippets = result.snippets.get("has_count_distinct", [])
        assert len(snippets) == 1
        assert "COUNT" in snippets[0].upper()

    def test_non_equi_join_snippet(self):
        result = parse_query("SELECT * FROM a JOIN b ON a.val > b.val")
        snippets = result.snippets.get("has_non_equi_join", [])
        assert len(snippets) == 1
        assert ">" in snippets[0]

    def test_string_json_parsing_snippet(self):
        result = parse_query("SELECT get_json_object(payload, '$.name') FROM events")
        snippets = result.snippets.get("has_string_json_parsing", [])
        assert len(snippets) == 1
        assert "get_json_object" in snippets[0].lower()

    def test_having_without_agg_snippet(self):
        result = parse_query("SELECT dept, COUNT(*) FROM t GROUP BY dept HAVING dept = 'Sales'")
        snippets = result.snippets.get("has_having_without_agg", [])
        assert len(snippets) == 1
        assert "dept" in snippets[0].lower()

    def test_possible_udf_snippet(self):
        result = parse_query("SELECT udf_compute_tax(amount) FROM orders")
        snippets = result.snippets.get("has_possible_udf", [])
        assert len(snippets) == 1
        assert "udf_compute_tax" in snippets[0].lower()

    def test_order_by_without_limit_snippet(self):
        result = parse_query("SELECT id FROM t ORDER BY id")
        snippets = result.snippets.get("has_order_by_without_limit", [])
        assert len(snippets) == 1
        assert "ORDER" in snippets[0].upper()

    def test_unpartitioned_window_snippet(self):
        result = parse_query("SELECT ROW_NUMBER() OVER (ORDER BY id) FROM t")
        snippets = result.snippets.get("has_unpartitioned_window", [])
        assert len(snippets) == 1
        assert "ROW_NUMBER" in snippets[0].upper() or "OVER" in snippets[0].upper()

    def test_no_snippet_when_check_not_triggered(self):
        result = parse_query("SELECT id FROM t WHERE id = 1")
        assert result.snippets == {}


class TestMalformedInput:
    def test_empty_string(self):
        result = parse_query("")
        assert result.tables == []

    def test_garbage(self):
        result = parse_query("NOT VALID SQL AT ALL )()(")
        assert isinstance(result.tables, list)
