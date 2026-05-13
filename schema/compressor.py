"""
schema/compressor.py
Compresses a table schema dict into a compact JSON string for embedding.
Includes sample values if available to improve retrieval accuracy.
"""

import json
from typing import Any, Dict


def compress_table_schema(table: Dict[str, Any]) -> str:
    """
    Convert a table schema dict into a compact text string suitable
    for embedding and semantic search.

    Input format:
      {
        "table": "orders",
        "columns": [{"name": "order_id", "type": "integer"}, ...],
        "row_count": 12345
      }
    """
    tname = table.get("table", "unknown")
    columns = table.get("columns", [])
    row_count = table.get("row_count")

    col_strs = [f"{c['name']} ({c.get('type', 'unknown')})" for c in columns]
    col_text = ", ".join(col_strs)

    text = f"Table: {tname} | Columns: {col_text}"
    if row_count is not None:
        text += f" | Rows: {row_count}"

    # Also return as JSON for structured re-parsing
    return json.dumps({
        "table": tname,
        "columns": columns,
        "row_count": row_count,
        "text": text,
    })
