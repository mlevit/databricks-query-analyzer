"""Tests for backend.analyzers.ai_advisor._parse_ai_response."""

from backend.analyzers.ai_advisor import _parse_ai_response


class TestParseAIResponse:
    def test_standard_format(self):
        response = (
            "OPTIMIZED SQL:\n"
            "```sql\n"
            "SELECT id FROM t WHERE status = 'active'\n"
            "```\n"
            "EXPLANATION:\n"
            "Removed SELECT * and added a filter."
        )
        sql, explanation = _parse_ai_response(response, "SELECT * FROM t")
        assert "SELECT id FROM t" in sql
        assert "Removed SELECT" in explanation

    def test_no_sql_block(self):
        response = "No changes needed. The query is already optimal."
        sql, explanation = _parse_ai_response(response, "SELECT 1")
        assert sql == "SELECT 1"
        assert "No changes needed" in explanation

    def test_only_sql_block(self):
        response = (
            "Here is the rewrite:\n"
            "```sql\n"
            "SELECT id FROM t\n"
            "```\n"
            "The above removes unnecessary columns."
        )
        sql, explanation = _parse_ai_response(response, "SELECT * FROM t")
        assert "SELECT id FROM t" in sql
        assert "removes unnecessary" in explanation

    def test_empty_response(self):
        sql, explanation = _parse_ai_response("", "SELECT 1")
        assert sql == "SELECT 1"
        assert explanation == ""

    def test_explanation_after_code_fence(self):
        response = (
            "```sql\n"
            "SELECT 1\n"
            "```\n"
            "This simplifies the query."
        )
        sql, explanation = _parse_ai_response(response, "ORIGINAL")
        assert sql == "SELECT 1"
        assert "simplifies" in explanation

    def test_multiple_code_blocks(self):
        response = (
            "```sql\n"
            "SELECT a FROM t\n"
            "```\n"
            "And also:\n"
            "```sql\n"
            "SELECT b FROM t\n"
            "```\n"
            "EXPLANATION:\n"
            "Two options provided."
        )
        sql, explanation = _parse_ai_response(response, "ORIGINAL")
        assert "SELECT a FROM t" in sql
        assert "Two options" in explanation

    def test_explanation_with_inline_code(self):
        response = (
            "OPTIMIZED SQL:\n"
            "```sql\n"
            "SELECT 1\n"
            "```\n"
            "EXPLANATION:\n"
            "```note\nsome note\n```\n"
            "The real explanation is here."
        )
        sql, explanation = _parse_ai_response(response, "ORIGINAL")
        assert sql == "SELECT 1"
        assert "real explanation" in explanation
