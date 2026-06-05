import psycopg2
import psycopg2.extras
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL database adapter using psycopg2."""

    def __init__(self):
        self.conn = None
        self.schema = settings.DB_SCHEMA

    async def connect(self) -> None:
        """Connect to PostgreSQL database."""
        if settings.DATABASE_URL:
            self.conn = psycopg2.connect(settings.DATABASE_URL)
        else:
            self.conn = psycopg2.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                dbname=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD
            )
        logger.info("Connected to PostgreSQL.")

    async def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from PostgreSQL.")

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            if cur.description:
                result = cur.fetchall()
                return [dict(row) for row in result]
            else:
                self.conn.commit()
                return [{"status": "Query executed successfully"}]

    async def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Fetch schema metadata from PostgreSQL."""
        query = """
        SELECT DISTINCT
            c.table_schema, c.table_name, c.column_name, c.data_type, c.ordinal_position,
            tc.constraint_type, kcu.constraint_name,
            ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
        FROM information_schema.columns c
        LEFT JOIN information_schema.key_column_usage kcu
            ON c.table_name = kcu.table_name AND c.column_name = kcu.column_name AND c.table_schema = kcu.table_schema
        LEFT JOIN information_schema.table_constraints tc
            ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE c.table_schema = %s
        ORDER BY c.table_name, c.ordinal_position;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (self.schema,))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            raw_rows = [dict(zip(columns, row)) for row in rows]
        return self._structure_metadata(raw_rows)

    def _structure_metadata(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Structure raw rows into unified schema format."""
        schema_dict = defaultdict(lambda: {"table": "", "columns": []})
        for row in rows:
            table = row["table_name"]
            schema_name = row["table_schema"]
            full_table_name = f"{schema_name}.{table}"
            column = {"name": row["column_name"], "type": row["data_type"]}
            if row.get("constraint_type") == "PRIMARY KEY":
                column["primary_key"] = True
            elif row.get("constraint_type") == "FOREIGN KEY":
                column["foreign_key"] = {
                    "table": f"{schema_name}.{row['foreign_table_name']}",
                    "column": row["foreign_column_name"]
                }
            schema_dict[table]["table"] = full_table_name
            schema_dict[table]["columns"].append(column)
        return list(schema_dict.values())

    def get_dialect_name(self) -> str:
        return "postgresql"
