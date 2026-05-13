"""
sandbox/sql_sandbox.py
AST-level SQL validation using sqlglot.
Blocks all DML/DDL write operations before any query reaches the database.
"""

from typing import Tuple

import sqlglot
import sqlglot.expressions as exp

# Blocked statement types (write operations)
_BLOCKED_TYPES = (
    exp.Drop,
    exp.Delete,
    exp.Update,
    exp.Insert,
    exp.Alter,        # covers ALTER TABLE
    exp.Create,
    exp.Command,      # covers arbitrary COPY, VACUUM, etc.
    exp.Transaction,
    exp.Grant,
)

# Also block by class name for newer sqlglot versions that add new node types
_BLOCKED_CLASS_NAMES = {
    "TruncateTable", "Truncate", "Revoke", "AlterTable",
}

# Blocked function names (extra caution)
_BLOCKED_FUNCTIONS = {
    "pg_read_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "copy",
    "dblink", "dblink_exec",
}


def validate_sql(sql: str, dialect: str = "postgres") -> Tuple[bool, str]:
    """
    Parse and validate SQL.
    Returns (True, "") if safe, (False, reason) if blocked.
    """
    sql_stripped = sql.strip()
    if not sql_stripped:
        return False, "Empty query"

    try:
        statements = sqlglot.parse(sql_stripped, dialect=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except sqlglot.errors.ParseError as e:
        return False, f"SQL parse error: {e}"

    if not statements:
        return False, "No valid SQL statement found"

    for stmt in statements:
        if stmt is None:
            continue

        # Block write statement types
        if isinstance(stmt, _BLOCKED_TYPES):
            return False, f"Blocked statement type: {type(stmt).__name__}"
        if type(stmt).__name__ in _BLOCKED_CLASS_NAMES:
            return False, f"Blocked statement type: {type(stmt).__name__}"

        # Walk AST for any write nodes embedded in CTEs, subqueries, etc.
        for node in stmt.walk():
            if isinstance(node, _BLOCKED_TYPES):
                return False, f"Blocked operation in query: {type(node).__name__}"
            if type(node).__name__ in _BLOCKED_CLASS_NAMES:
                return False, f"Blocked operation in query: {type(node).__name__}"

            # Block dangerous function calls
            if isinstance(node, exp.Anonymous):
                fname = (node.name or "").lower()
                if fname in _BLOCKED_FUNCTIONS:
                    return False, f"Blocked function: {fname}"

    return True, ""
