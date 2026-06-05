import sqlite3
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class SQLiteDatabase(BaseDatabase):
    """SQLite database adapter using built-in sqlite3."""

    def __init__(self):
        self.conn = None
        self.db_path = settings.SQLITE_DB_PATH

    async def connect(self) -> None:
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info("Connected to SQLite at %s", self.db_path)

    async def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Disconnected from SQLite.")

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        with self.conn:
            cur = self.conn.execute(sql)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]
            else:
                self.conn.commit()
                return [{"status": "Query executed successfully"}]

    async def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Fetch schema metadata from SQLite using PRAGMA."""
        tables = []
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        for row in cur.fetchall():
            tables.append(row[0])

        result = []
        for table in tables:
            columns = []
            # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
            cur = self.conn.execute(f"PRAGMA table_info({table})")
            col_info = {row[1]: {"type": row[2], "pk": row[5]} for row in cur.fetchall()}

            # PRAGMA foreign_key_list returns: id, seq, table, from, to, on_update, on_delete, match
            cur = self.conn.execute(f"PRAGMA foreign_key_list({table})")
            fk_info = {}
            for row in cur.fetchall():
                fk_info[row[3]] = {"table": row[2], "column": row[4]}

            for col_name, info in col_info.items():
                col = {"name": col_name, "type": info["type"]}
                if info["pk"]:
                    col["primary_key"] = True
                if col_name in fk_info:
                    col["foreign_key"] = {
                        "table": fk_info[col_name]["table"],
                        "column": fk_info[col_name]["column"]
                    }
                columns.append(col)

            result.append({"table": table, "columns": columns})
        return result

    def get_dialect_name(self) -> str:
        return "sqlite"
