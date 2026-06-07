import oracledb
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class OracleDatabase(BaseDatabase):
    """Oracle database adapter using oracledb."""

    def __init__(self):
        self.conn = None
        self.schema = settings.DB_SCHEMA.upper()

    async def connect(self) -> None:
        """Connect to Oracle database."""
        if settings.DATABASE_URL:
            self.conn = oracledb.connect(settings.DATABASE_URL)
        else:
            dsn = f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            self.conn = oracledb.connect(
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                dsn=dsn
            )
        logger.info("Connected to Oracle.")

    async def disconnect(self) -> None:
        """Close Oracle connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from Oracle.")

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
        """Fetch schema metadata from Oracle."""
        query = """
        SELECT
            c.OWNER AS table_schema, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.COLUMN_ID AS ordinal_position,
            ac.CONSTRAINT_TYPE, acc.CONSTRAINT_NAME,
            acc2.TABLE_NAME AS foreign_table_name, acc2.COLUMN_NAME AS foreign_column_name
        FROM ALL_TAB_COLUMNS c
        LEFT JOIN ALL_CONS_COLUMNS acc
            ON c.TABLE_NAME = acc.TABLE_NAME AND c.COLUMN_NAME = acc.COLUMN_NAME AND c.OWNER = acc.OWNER
        LEFT JOIN ALL_CONSTRAINTS ac
            ON acc.CONSTRAINT_NAME = ac.CONSTRAINT_NAME AND acc.OWNER = ac.OWNER
        LEFT JOIN ALL_CONS_COLUMNS acc2
            ON ac.R_CONSTRAINT_NAME = acc2.CONSTRAINT_NAME AND ac.OWNER = acc2.OWNER
        WHERE c.OWNER = :schema_name
        ORDER BY c.TABLE_NAME, c.COLUMN_ID
        """
        with self.conn.cursor() as cur:
            cur.execute(query, {"schema_name": self.schema})
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
            if row.get("CONSTRAINT_TYPE") == "P":
                column["primary_key"] = True
            elif row.get("CONSTRAINT_TYPE") == "R":
                column["foreign_key"] = {
                    "table": f"{schema_name}.{row['FOREIGN_TABLE_NAME']}",
                    "column": row["FOREIGN_COLUMN_NAME"]
                }
            schema_dict[table]["table"] = full_table_name
            schema_dict[table]["columns"].append(column)
        return list(schema_dict.values())

    def get_dialect_name(self) -> str:
        return "oracle"
