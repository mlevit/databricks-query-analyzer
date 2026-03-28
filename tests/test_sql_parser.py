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


class TestMalformedInput:
    def test_empty_string(self):
        result = parse_query("")
        assert result.tables == []

    def test_garbage(self):
        result = parse_query("NOT VALID SQL AT ALL )()(")
        assert isinstance(result.tables, list)
