"""
connectors/base.py
Abstract connector interface + factory function.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd


class BaseConnector(ABC):
    """Common interface all data connectors must implement."""

    @abstractmethod
    def get_schema(self) -> List[Dict[str, Any]]:
        """Return list of {table, columns: [{name, type}], row_count}."""
        ...

    @abstractmethod
    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a read-only SQL query and return rows as list of dicts."""
        ...

    @abstractmethod
    def load_dataframe(self, table: Optional[str] = None) -> pd.DataFrame:
        """Load data as a pandas DataFrame (used by Python sandbox)."""
        ...


def get_connector(connector_id: str) -> BaseConnector:
    """
    Factory: parse connector_id string and return the right connector.

    connector_id formats:
      neon:<schema_name>
      csv:<supabase_public_url>
      sqlite:<supabase_public_url>
      sheets:<google_sheets_csv_export_url>
    """
    if connector_id.startswith("neon:"):
        from connectors.neon_connector import NeonConnector
        schema = connector_id.split(":", 1)[1]
        return NeonConnector(schema=schema)

    if connector_id.startswith("postgres-enc:"):
        from connectors.neon_connector import NeonConnector
        from connectors.crypto import decrypt_connection_string
        
        # Format is: postgres-enc:<base64_encrypted_db_url>[:schema_name]
        parts = connector_id.split(":")
        payload = parts[1]
        schema = parts[2] if len(parts) > 2 else "public"
        
        db_url = decrypt_connection_string(payload)
        return NeonConnector(schema=schema, db_url=db_url)

    if connector_id.startswith("csv:"):
        from connectors.csv_connector import CsvConnector
        url = connector_id.split(":", 1)[1]
        return CsvConnector(supabase_url=url)

    if connector_id.startswith("sqlite:"):
        from connectors.sqlite_connector import SqliteConnector
        url = connector_id.split(":", 1)[1]
        return SqliteConnector(supabase_url=url)

    if connector_id.startswith("sheets:"):
        from connectors.sheets_connector import SheetsConnector
        url = connector_id.split(":", 1)[1]
        return SheetsConnector(csv_export_url=url)

    raise ValueError(f"Unknown connector_id: {connector_id}")
