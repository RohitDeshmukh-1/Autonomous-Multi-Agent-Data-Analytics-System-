"""
tests/unit/test_schema_compressor.py
Tests for schema text compression used for vector embedding.
"""

import json
import pytest
from schema.compressor import compress_table_schema


@pytest.mark.unit
class TestCompressTableSchema:
    def test_basic_output_is_json(self):
        table = {
            "table": "orders",
            "columns": [{"name": "id", "type": "integer"}, {"name": "amount", "type": "numeric"}],
            "row_count": 100,
        }
        result = compress_table_schema(table)
        parsed = json.loads(result)
        assert parsed["table"] == "orders"

    def test_contains_table_name(self):
        table = {"table": "customers", "columns": [], "row_count": 0}
        result = compress_table_schema(table)
        assert "customers" in result

    def test_contains_column_names(self):
        table = {
            "table": "orders",
            "columns": [
                {"name": "order_id", "type": "integer"},
                {"name": "total_amount", "type": "numeric"},
            ],
            "row_count": 500,
        }
        result = compress_table_schema(table)
        assert "order_id" in result
        assert "total_amount" in result

    def test_contains_row_count(self):
        table = {"table": "events", "columns": [], "row_count": 9999}
        result = compress_table_schema(table)
        assert "9999" in result

    def test_no_row_count_ok(self):
        table = {"table": "logs", "columns": [], "row_count": None}
        result = compress_table_schema(table)
        parsed = json.loads(result)
        assert parsed["table"] == "logs"

    def test_parsed_columns_round_trip(self):
        columns = [
            {"name": "user_id", "type": "uuid"},
            {"name": "email", "type": "text"},
        ]
        table = {"table": "users", "columns": columns, "row_count": 42}
        parsed = json.loads(compress_table_schema(table))
        assert parsed["columns"] == columns

    def test_unknown_table_name(self):
        """Should not crash on missing table key."""
        table = {"columns": [], "row_count": 0}
        result = compress_table_schema(table)
        assert "unknown" in result

    def test_text_field_present(self):
        table = {"table": "sales", "columns": [{"name": "amount", "type": "numeric"}], "row_count": 10}
        parsed = json.loads(compress_table_schema(table))
        assert "text" in parsed
        assert "sales" in parsed["text"]
