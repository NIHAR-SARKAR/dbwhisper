"""Legacy schema loader - now delegates to database factory.

Kept for backward compatibility. Use DatabaseFactory.get_database() directly.
"""
import logging
from app.services.db_factory import DatabaseFactory
from app.util.config import settings

logger = logging.getLogger(__name__)


async def get_schema_context(schema_name: str = None) -> str:
    """Get schema context as JSON string. Delegates to the active database adapter."""
    db = None
    try:
        db = DatabaseFactory.get_database(settings.DB_TYPE)
        await db.connect()
        metadata = await db.get_schema_metadata()
        import json
        return json.dumps(metadata, indent=2)
    except Exception as e:
        logger.exception("Error loading schema context")
        raise
    finally:
        if db:
            try:
                await db.disconnect()
            except Exception:
                pass
