import pymysql
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class MySQLDatabase(BaseDatabase):
    """MySQL database adapter using PyMySQL."""

    def __init__(self):
        self.conn = None
        self.schema = settings.DB_SCHEMA

    async def connect(self) -> None:
        """Connect to MySQL database."""
        self.conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.info("Connected to MySQL.")

    async def disconnect(self) -> None:
        """Close MySQL connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from MySQL.")

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        with self.conn.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                return cur.fetchall()
            else:
                self.conn.commit()
                return [{"status": "Query executed successfully"}]

    async def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Fetch schema metadata from MySQL."""
        query = """
        SELECT
            c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.ORDINAL_POSITION,
            tc.CONSTRAINT_TYPE, kcu.CONSTRAINT_NAME,
            kcu.REFERENCED_TABLE_NAME AS foreign_table_name,
            kcu.REFERENCED_COLUMN_NAME AS foreign_column_name
        FROM information_schema.COLUMNS c
        LEFT JOIN information_schema.KEY_COLUMN_USAGE kcu
            ON c.TABLE_NAME = kcu.TABLE_NAME AND c.COLUMN_NAME = kcu.COLUMN_NAME AND c.TABLE_SCHEMA = kcu.TABLE_SCHEMA
        LEFT JOIN information_schema.TABLE_CONSTRAINTS tc
            ON kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
        WHERE c.TABLE_SCHEMA = %s
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (self.schema,))
            rows = cur.fetchall()
        return self._structure_metadata(rows)

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
        return "mysql"
