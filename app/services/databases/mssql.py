"""Microsoft SQL Server database adapter using aioodbc with connection pooling."""

import aioodbc
import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional
from .base import BaseDatabase
from app.util.config import settings

logger = logging.getLogger(__name__)


class MSSQLDatabase(BaseDatabase):
    """MSSQL database adapter using aioodbc with connection pooling."""

    def __init__(self):
        self.pool: Optional[aioodbc.Pool] = None
        self.schema = settings.DB_SCHEMA or "dbo"  # Default to dbo if not set

    async def connect(self) -> None:
        # Handle port: SQL Server default is 1433, only append if non-default
        port = getattr(settings, 'DB_PORT', 1433)
        server = settings.DB_HOST
        if port and str(port) != "1433":
            server = f"{server},{port}"
        
        # Try multiple driver names since installed driver may vary
        drivers = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server Native Client 11.0",
            "SQL Server",
        ]
        
        conn_str = None
        last_error = None
        
        for driver in drivers:
            try:
                test_conn_str = (
                    f"DRIVER={{{driver}}};"
                    f"SERVER={server};"
                    f"DATABASE={settings.DB_NAME};"
                    f"UID={settings.DB_USER};"
                    f"PWD={settings.DB_PASSWORD};"
                    f"TrustServerCertificate=yes;"  # Required for Driver 18+
                )
                # Test connection immediately
                self.pool = await aioodbc.create_pool(
                    dsn=test_conn_str, 
                    min_size=2, 
                    max_size=10
                )
                conn_str = test_conn_str
                logger.info(f"MSSQL pool created using driver: {driver}")
                break
            except Exception as e:
                last_error = e
                continue
        
        if not conn_str:
            raise ConnectionError(
                f"Failed to connect to SQL Server with any ODBC driver. "
                f"Last error: {last_error}"
            )

    async def disconnect(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            logger.info("MSSQL pool closed.")

    async def execute_query(self, sql: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")
            
        sql = self._inject_limit(sql, limit)
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = await cur.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                return [{"status": "Query executed successfully"}]

    def _inject_limit(self, sql: str, limit: int) -> str:
        stripped = sql.strip()
        lower_stripped = stripped.lower()
        if lower_stripped.startswith("select") and "top" not in lower_stripped and "limit" not in lower_stripped:
            # Find the position after "select" (handle extra whitespace)
            idx = lower_stripped.find("select") + 6
            return f"SELECT TOP {limit}" + stripped[idx:]
        return sql

    async def get_schema_metadata(self) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")
    
        # Verify we're in the right database first
        verify_query = "SELECT DB_NAME(), SCHEMA_NAME()"
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(verify_query)
                db_name, default_schema = await cur.fetchone()
                logger.info(f"Connected to database: {db_name}, default schema: {default_schema}")
    
        # Use parameterized query with ? placeholder (safer)
        query = """
        SELECT
            c.table_schema, 
            c.table_name, 
            c.column_name, 
            c.data_type, 
            c.ordinal_position,
            tc.constraint_type, 
            kcu.constraint_name,
            ccu.table_name AS foreign_table_name, 
            ccu.column_name AS foreign_column_name
        FROM information_schema.columns c
        LEFT JOIN information_schema.key_column_usage kcu
            ON c.table_name = kcu.table_name 
            AND c.column_name = kcu.column_name 
            AND c.table_schema = kcu.table_schema
        LEFT JOIN information_schema.table_constraints tc
            ON kcu.constraint_name = tc.constraint_name 
            AND kcu.table_schema = tc.table_schema
            AND kcu.table_name = tc.table_name
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
            AND tc.constraint_type = 'FOREIGN KEY'
        WHERE c.table_schema = ?
        ORDER BY c.table_name, c.ordinal_position;
        """
    
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                logger.info(f"Executing schema query for schema: '{self.schema}'")
                await cur.execute(query, (self.schema,))
                
                # CRITICAL FIX: Handle None description when 0 rows returned
                if cur.description is None:
                    logger.error(
                        f"Schema query returned no result set for schema '{self.schema}'. "
                        f"This usually means: (1) Wrong database (connected to '{db_name}'), "
                        f"(2) Schema '{self.schema}' doesn't exist in this database, or "
                        f"(3) User lacks VIEW DEFINITION permission."
                    )
                    return []
                
                columns = [desc[0] for desc in cur.description]
                rows = await cur.fetchall()
                logger.info(f"Total rows fetched: {len(rows)}")
                
                if not rows:
                    logger.warning(f"Schema '{self.schema}' exists but has no tables.")
                    return []
                
                raw_rows = [dict(zip(columns, row)) for row in rows]
    
        return self._structure_metadata(raw_rows)

    def _structure_metadata(self, rows):
        schema_dict = defaultdict(lambda: {"table": "", "columns": {}})
        for row in rows:
            table = row["table_name"]
            schema_name = row["table_schema"]
            full_table_name = f"{schema_name}.{table}"
            col_name = row["column_name"]

            if col_name not in schema_dict[table]["columns"]:
                schema_dict[table]["columns"][col_name] = {
                    "name": col_name,
                    "type": row["data_type"]
                }

            column = schema_dict[table]["columns"][col_name]
            constraint_type = row.get("constraint_type")
            if constraint_type == "PRIMARY KEY":
                column["primary_key"] = True
            elif constraint_type == "FOREIGN KEY":
                ref_table = row.get("foreign_table_name")
                ref_column = row.get("foreign_column_name")
                if ref_table and ref_column:
                    column["foreign_key"] = {
                        "table": f"{schema_name}.{ref_table}",
                        "column": ref_column
                    }

            schema_dict[table]["table"] = full_table_name

        return [
            {"table": v["table"], "columns": list(v["columns"].values())}
            for v in schema_dict.values()
        ]

    def get_dialect_name(self) -> str:
        return "mssql"

    async def explain_query(self, sql: str) -> Dict[str, Any]:
        if not self.pool:
            raise RuntimeError("Database not connected. Call connect() first.")
            
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # SHOWPLAN_XML must be set in its own batch, then the query executed separately
                await cur.execute("SET SHOWPLAN_XML ON;")
                await cur.execute(sql)
                
                # May need to fetch multiple results
                plan_xml = ""
                while True:
                    if cur.description:
                        row = await cur.fetchone()
                        if row and row[0]:
                            plan_xml = row[0]
                    if not await cur.nextset():
                        break
                
                await cur.execute("SET SHOWPLAN_XML OFF;")
                return {"plan_xml": plan_xml}