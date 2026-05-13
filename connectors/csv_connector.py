"""
connectors/csv_connector.py
Downloads a CSV from Supabase Storage, loads it into in-memory SQLite,
and exposes it as a BaseConnector.
"""

import io
import sqlite3
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from connectors.base import BaseConnector


class CsvConnector(BaseConnector):
    """
    Downloads CSV bytes from a Supabase public URL, loads into in-memory
    SQLite as table `data`, and runs queries against it.
    """

    def __init__(self, supabase_url: str, file_bytes: Optional[bytes] = None):
        self.supabase_url = supabase_url
        self._df: Optional[pd.DataFrame] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._file_bytes = file_bytes
        self._init()

    def _fetch_bytes(self) -> bytes:
        if self._file_bytes:
            return self._file_bytes
        resp = requests.get(self.supabase_url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def _init(self):
        raw = self._fetch_bytes()
        self._df = pd.read_csv(io.BytesIO(raw))
        # Normalise column names
        self._df.columns = [c.strip().lower().replace(" ", "_") for c in self._df.columns]

        # Load into in-memory SQLite
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._df.to_sql("data", self._conn, if_exists="replace", index=False)

    def get_schema(self) -> List[Dict[str, Any]]:
        df = self._df
        columns = [{"name": col, "type": str(df[col].dtype)} for col in df.columns]
        return [{"table": "data", "columns": columns, "row_count": len(df)}]

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def load_dataframe(self, table: Optional[str] = None) -> pd.DataFrame:
        return self._df.copy()
