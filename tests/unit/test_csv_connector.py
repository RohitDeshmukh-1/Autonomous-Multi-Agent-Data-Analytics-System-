"""
tests/unit/test_csv_connector.py
Tests for CsvConnector — uses in-memory bytes, no network calls.
"""

import pytest
import pandas as pd
from connectors.csv_connector import CsvConnector


@pytest.fixture
def csv_bytes():
    return (
        b"order_id,customer,product,amount,region\n"
        b"1,Alice,Widget,99.99,North\n"
        b"2,Bob,Gadget,149.99,South\n"
        b"3,Alice,Doohickey,49.99,North\n"
        b"4,Carol,Widget,99.99,East\n"
        b"5,Dave,Gadget,149.99,West\n"
    )


@pytest.fixture
def connector(csv_bytes):
    return CsvConnector(supabase_url="http://fake", file_bytes=csv_bytes)


@pytest.mark.unit
class TestCsvConnector:
    def test_get_schema_returns_one_table(self, connector):
        schema = connector.get_schema()
        assert len(schema) == 1
        assert schema[0]["table"] == "data"

    def test_get_schema_has_correct_columns(self, connector):
        cols = {c["name"] for c in connector.get_schema()[0]["columns"]}
        assert cols == {"order_id", "customer", "product", "amount", "region"}

    def test_get_schema_row_count(self, connector):
        schema = connector.get_schema()
        assert schema[0]["row_count"] == 5

    def test_execute_sql_select_all(self, connector):
        rows = connector.execute_sql("SELECT * FROM data")
        assert len(rows) == 5
        assert "customer" in rows[0]

    def test_execute_sql_where(self, connector):
        rows = connector.execute_sql("SELECT * FROM data WHERE region = 'North'")
        assert len(rows) == 2
        assert all(r["region"] == "North" for r in rows)

    def test_execute_sql_aggregation(self, connector):
        rows = connector.execute_sql(
            "SELECT product, COUNT(*) as cnt FROM data GROUP BY product ORDER BY cnt DESC"
        )
        assert len(rows) >= 1
        products = [r["product"] for r in rows]
        assert "Widget" in products

    def test_execute_sql_limit(self, connector):
        rows = connector.execute_sql("SELECT * FROM data LIMIT 2")
        assert len(rows) == 2

    def test_load_dataframe(self, connector):
        df = connector.load_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "amount" in df.columns

    def test_column_names_normalised(self, connector):
        """Spaces in headers should be replaced with underscores."""
        csv_with_spaces = b"order id,customer name,total amount\n1,Alice,99.99\n"
        c = CsvConnector(supabase_url="http://fake", file_bytes=csv_with_spaces)
        schema = c.get_schema()
        col_names = {col["name"] for col in schema[0]["columns"]}
        assert "order_id" in col_names
        assert "customer_name" in col_names

    def test_sql_sum(self, connector):
        rows = connector.execute_sql("SELECT SUM(amount) as total FROM data")
        assert rows[0]["total"] == pytest.approx(549.95, rel=1e-3)
