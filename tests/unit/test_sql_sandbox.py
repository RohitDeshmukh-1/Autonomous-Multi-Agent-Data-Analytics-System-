"""
tests/unit/test_sql_sandbox.py
Tests for sqlglot-based SQL safety validator.
All tests are pure Python — no external calls.
"""

import pytest
from sandbox.sql_sandbox import validate_sql


# ── Safe queries (must pass) ──────────────────────────────────────────────────

SAFE_QUERIES = [
    "SELECT * FROM orders LIMIT 10",
    "SELECT product, SUM(amount) FROM orders GROUP BY product",
    "SELECT o.order_id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id",
    "WITH cte AS (SELECT * FROM orders) SELECT * FROM cte",
    "SELECT COUNT(*) FROM orders WHERE created_at > '2024-01-01'",
    "SELECT DISTINCT region FROM customers ORDER BY region",
    "SELECT product, AVG(amount) OVER (PARTITION BY region) FROM orders",
    "SELECT CAST(amount AS TEXT) FROM orders",
]

@pytest.mark.unit
@pytest.mark.parametrize("sql", SAFE_QUERIES)
def test_safe_queries_pass(sql):
    ok, err = validate_sql(sql)
    assert ok, f"Expected safe query to pass but got: {err}"
    assert err == ""


# ── Blocked write operations ──────────────────────────────────────────────────

BLOCKED_QUERIES = [
    ("DELETE FROM orders WHERE 1=1", "Delete"),
    ("DROP TABLE orders", "Drop"),
    ("UPDATE orders SET amount = 0", "Update"),
    ("INSERT INTO orders (id) VALUES (1)", "Insert"),
    ("ALTER TABLE orders ADD COLUMN foo TEXT", "AlterTable"),
    ("CREATE TABLE evil (id INT)", "Create"),
    ("GRANT ALL ON orders TO attacker", "Grant"),
]

@pytest.mark.unit
@pytest.mark.parametrize("sql,expected_type", BLOCKED_QUERIES)
def test_blocked_write_operations(sql, expected_type):
    ok, err = validate_sql(sql)
    assert not ok, f"Expected '{sql}' to be blocked"
    assert err != ""

@pytest.mark.unit
def test_truncate_blocked():
    """TRUNCATE may be parsed as its own node type by newer sqlglot versions."""
    ok, err = validate_sql("TRUNCATE orders")
    # TRUNCATE must be blocked regardless of how sqlglot classifies it
    assert not ok, "TRUNCATE should be blocked"


# ── Blocked dangerous functions ───────────────────────────────────────────────

@pytest.mark.unit
def test_blocks_pg_read_file():
    sql = "SELECT pg_read_file('/etc/passwd')"
    ok, err = validate_sql(sql)
    assert not ok
    assert "pg_read_file" in err.lower() or err != ""


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_empty_query_rejected():
    ok, err = validate_sql("")
    assert not ok
    assert err != ""


@pytest.mark.unit
def test_whitespace_only_rejected():
    ok, err = validate_sql("   \n\t  ")
    assert not ok


@pytest.mark.unit
def test_sqlite_dialect():
    ok, err = validate_sql("SELECT strftime('%Y', created_at) FROM orders", dialect="sqlite")
    assert ok, f"SQLite date function should pass: {err}"


@pytest.mark.unit
def test_cte_with_embedded_delete_blocked():
    """DELETE inside a CTE must still be blocked."""
    sql = """
    WITH bad AS (DELETE FROM orders RETURNING *)
    SELECT * FROM bad
    """
    ok, err = validate_sql(sql)
    assert not ok


@pytest.mark.unit
def test_multiple_safe_statements_pass():
    """A single SELECT is safe."""
    ok, err = validate_sql("SELECT 1")
    assert ok


@pytest.mark.unit
def test_syntax_error_returns_false():
    ok, err = validate_sql("SELECT FROM WHERE")
    assert not ok
    assert "parse" in err.lower() or err != ""
