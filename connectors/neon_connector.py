"""
connectors/neon_connector.py
Connects to Neon serverless Postgres. Uses connection pool.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2.extras

from connectors.base import BaseConnector
from db.pool import pooled_connection, pooled_cursor


class NeonConnector(BaseConnector):
    def __init__(self, schema: str = "public"):
        self.schema = schema

    def get_schema(self) -> List[Dict[str, Any]]:
        with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
            cur.execute(
                """
                SELECT
                    t.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.character_maximum_length
                FROM information_schema.tables t
                JOIN information_schema.columns c
                    ON c.table_name = t.table_name
                    AND c.table_schema = t.table_schema
                WHERE t.table_schema = %s
                  AND t.table_type = 'BASE TABLE'
                  AND t.table_name NOT IN
                      ('sessions','query_history','schema_embeddings',
                       'memory_embeddings','dashboards','dashboard_panels')
                ORDER BY t.table_name, c.ordinal_position
                """,
                (self.schema,),
            )
            rows = cur.fetchall()

            # Group by table
            tables: Dict[str, Dict] = {}
            for row in rows:
                tname = row["table_name"]
                if tname not in tables:
                    tables[tname] = {"table": tname, "columns": []}
                tables[tname]["columns"].append(
                    {"name": row["column_name"], "type": row["data_type"]}
                )

            # Add row counts
            result = []
            for tname, tdata in tables.items():
                try:
                    cur.execute(f'SELECT COUNT(*) FROM "{self.schema}"."{tname}"')
                    tdata["row_count"] = cur.fetchone()["count"]
                except Exception:
                    tdata["row_count"] = None
                result.append(tdata)

            return result

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        with pooled_cursor(readonly=True, dict_cursor=True) as (cur, conn):
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def load_dataframe(self, table: Optional[str] = None) -> pd.DataFrame:
        if table:
            import os
            db_url = os.environ["NEON_DATABASE_URL"]
            return pd.read_sql(
                f'SELECT * FROM "{self.schema}"."{table}" LIMIT 100000',
                db_url,
            )
        raise ValueError("NeonConnector.load_dataframe requires a table name")
