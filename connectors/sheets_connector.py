"""
connectors/sheets_connector.py
Fetches a Google Sheet exported as CSV and delegates to CsvConnector.
Expects a CSV export URL like:
  https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=0
"""

import requests
from connectors.base import BaseConnector
from connectors.csv_connector import CsvConnector
from typing import Any, Dict, List, Optional
import pandas as pd


class SheetsConnector(BaseConnector):
    def __init__(self, csv_export_url: str):
        self.csv_export_url = csv_export_url
        resp = requests.get(csv_export_url, timeout=30)
        resp.raise_for_status()
        self._delegate = CsvConnector(
            supabase_url=csv_export_url,
            file_bytes=resp.content,
        )

    def get_schema(self) -> List[Dict[str, Any]]:
        return self._delegate.get_schema()

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        return self._delegate.execute_sql(sql)

    def load_dataframe(self, table: Optional[str] = None) -> pd.DataFrame:
        return self._delegate.load_dataframe(table)
