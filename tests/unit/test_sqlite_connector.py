"""
tests/unit/test_sqlite_connector.py
Tests for SqliteConnector using a real in-memory SQLite file written to /tmp.
No network calls.
"""

import os
import sqlite3
import tempfile

import pandas as pd
import pytest


@pytest.fixture
def sqlite_file_bytes():
    """Create a real SQLite file in /tmp and return its bytes."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = f.name

    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, region TEXT, amount REAL)")
    conn.execute("INSERT INTO sales VALUES (1, 'North', 100.0)")
    conn.execute("INSERT INTO sales VALUES (2, 'South', 200.0)")
    conn.execute("INSERT INTO sales VALUES (3, 'North', 150.0)")
    conn.commit()
    conn.close()

    with open(path, "rb") as f:
        data = f.read()

    os.unlink(path)
    return data


@pytest.fixture
def sqlite_connector(sqlite_file_bytes, mocker):
    """SqliteConnector with mocked HTTP download."""
    mock_resp = mocker.MagicMock()
    mock_resp.content = sqlite_file_bytes
    mock_resp.raise_for_status.return_value = None
    mocker.patch("requests.get", return_value=mock_resp)

    from connectors.sqlite_connector import SqliteConnector
    return SqliteConnector(supabase_url="http://fake/file.sqlite")


@pytest.mark.unit
class TestSqliteConnector:
    def test_get_schema_lists_tables(self, sqlite_connector):
        schema = sqlite_connector.get_schema()
        table_names = [t["table"] for t in schema]
        assert "sales" in table_names

    def test_get_schema_has_columns(self, sqlite_connector):
        schema = sqlite_connector.get_schema()
        sales = next(t for t in schema if t["table"] == "sales")
        col_names = {c["name"] for c in sales["columns"]}
        assert "region" in col_names
        assert "amount" in col_names

    def test_get_schema_row_count(self, sqlite_connector):
        schema = sqlite_connector.get_schema()
        sales = next(t for t in schema if t["table"] == "sales")
        assert sales["row_count"] == 3

    def test_execute_sql_select_all(self, sqlite_connector):
        rows = sqlite_connector.execute_sql("SELECT * FROM sales")
        assert len(rows) == 3

    def test_execute_sql_where_clause(self, sqlite_connector):
        rows = sqlite_connector.execute_sql("SELECT * FROM sales WHERE region = 'North'")
        assert len(rows) == 2

    def test_execute_sql_aggregation(self, sqlite_connector):
        rows = sqlite_connector.execute_sql("SELECT SUM(amount) as total FROM sales")
        assert rows[0]["total"] == pytest.approx(450.0)

    def test_load_dataframe_returns_dataframe(self, sqlite_connector):
        df = sqlite_connector.load_dataframe(table="sales")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_load_dataframe_without_table_uses_first(self, sqlite_connector):
        df = sqlite_connector.load_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
