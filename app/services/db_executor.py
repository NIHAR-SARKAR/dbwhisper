"""Legacy database executor - now delegates to database factory.

Kept for backward compatibility. Use DatabaseFactory.get_database() directly.
"""
import logging
from app.services.db_factory import DatabaseFactory
from app.util.config import settings

logger = logging.getLogger(__name__)


async def run_sql_query(query: str) -> str:
    """Execute SQL query and return JSON string result. Delegates to the active database adapter."""
    db = None
    try:
        db = DatabaseFactory.get_database(settings.DB_TYPE)
        await db.connect()
        result = await db.execute_query(query)
        import json
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.exception("Error executing SQL query")
        return json.dumps({"error": str(e)})
    finally:
        if db:
            try:
                await db.disconnect()
            except Exception:
                pass
