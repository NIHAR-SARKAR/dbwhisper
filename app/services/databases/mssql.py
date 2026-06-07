import pyodbc
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class MSSQLDatabase(BaseDatabase):
    """Microsoft SQL Server database adapter using pyodbc."""

    def __init__(self):
        self.conn = None
        self.schema = settings.DB_SCHEMA

    async def connect(self) -> None:
        """Connect to MSSQL database."""
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={settings.DB_HOST},{settings.DB_PORT};"
            f"DATABASE={settings.DB_NAME};"
            f"UID={settings.DB_USER};"
            f"PWD={settings.DB_PASSWORD}"
        )
        self.conn = pyodbc.connect(conn_str)
        logger.info("Connected to MSSQL.")

    async def disconnect(self) -> None:
        """Close MSSQL connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from MSSQL.")

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        with self.conn.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                self.conn.commit()
                return [{"status": "Query executed successfully"}]

    async def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Fetch schema metadata from MSSQL."""
        query = """
        SELECT
            c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.ORDINAL_POSITION,
            tc.CONSTRAINT_TYPE, kcu.CONSTRAINT_NAME,
            ccu.TABLE_NAME AS foreign_table_name, ccu.COLUMN_NAME AS foreign_column_name
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON c.TABLE_NAME = kcu.TABLE_NAME AND c.COLUMN_NAME = kcu.COLUMN_NAME AND c.TABLE_SCHEMA = kcu.TABLE_SCHEMA
        LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
        LEFT JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
            ON tc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
        WHERE c.TABLE_SCHEMA = ?
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (self.schema,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            raw_rows = [dict(zip(columns, row)) for row in rows]
        return self._structure_metadata(raw_rows)

    def _structure_metadata(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Structure raw rows into unified schema format."""
        schema_dict = defaultdict(lambda: {"table": "", "columns": []})
        for row in rows:
            table = row["TABLE_NAME"]
            schema_name = row["TABLE_SCHEMA"]
            full_table_name = f"{schema_name}.{table}"
            column = {"name": row["COLUMN_NAME"], "type": row["DATA_TYPE"]}
            if row.get("CONSTRAINT_TYPE") == "PRIMARY KEY":
                column["primary_key"] = True
            elif row.get("CONSTRAINT_TYPE") == "FOREIGN KEY":
                column["foreign_key"] = {
                    "table": f"{schema_name}.{row['foreign_table_name']}",
                    "column": row["foreign_column_name"]
                }
            schema_dict[table]["table"] = full_table_name
            schema_dict[table]["columns"].append(column)
        return list(schema_dict.values())

    def get_dialect_name(self) -> str:
        return "mssql"
