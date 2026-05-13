"""
connectors/sqlite_connector.py
Downloads a SQLite file from Supabase Storage and queries it in-memory.
"""

import io
import sqlite3
import tempfile
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from connectors.base import BaseConnector


class SqliteConnector(BaseConnector):
    def __init__(self, supabase_url: str):
        self.supabase_url = supabase_url
        self._tmpfile = None
        self._conn: Optional[sqlite3.Connection] = None
        self._init()

    def _init(self):
        resp = requests.get(self.supabase_url, timeout=30)
        resp.raise_for_status()
        # Write to a temp file (SQLite needs a real file path for some features)
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmpfile.write(resp.content)
        self._tmpfile.flush()
        self._conn = sqlite3.connect(self._tmpfile.name, check_same_thread=False)

    def get_schema(self) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        result = []
        for tname in tables:
            cur.execute(f'PRAGMA table_info("{tname}")')
            columns = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
            cur.execute(f'SELECT COUNT(*) FROM "{tname}"')
            row_count = cur.fetchone()[0]
            result.append({"table": tname, "columns": columns, "row_count": row_count})
        return result

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def load_dataframe(self, table: Optional[str] = None) -> pd.DataFrame:
        if table:
            return pd.read_sql(f'SELECT * FROM "{table}"', self._conn)
        # Return first table
        cur = self._conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        row = cur.fetchone()
        if row:
            return pd.read_sql(f'SELECT * FROM "{row[0]}"', self._conn)
        raise ValueError("No tables found in SQLite file")

    def __del__(self):
        if self._conn:
            self._conn.close()
        if self._tmpfile:
            try:
                os.unlink(self._tmpfile.name)
            except Exception:
                pass
