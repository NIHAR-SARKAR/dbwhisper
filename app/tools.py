import json
import logging
import re
from app.services.llm_factory import LLMFactory
from app.services.db_factory import DatabaseFactory
from app.services.domain_context import load_domain_context
from app.util.config import settings

logger = logging.getLogger(__name__)


async def handle_user_query(task_input: str) -> str:
    """Handle natural language query: generate SQL via LLM, execute via DB, return results."""
    db = None
    sql_clean = None
    try:
        # 1. Get database adapter
        db = DatabaseFactory.get_database(settings.DB_TYPE)
        await db.connect()

        # 2. Get schema metadata
        schema_metadata = await db.get_schema_metadata()
        schema_json = json.dumps(schema_metadata, indent=2)

        # 3. Load domain context
        domain_context = await load_domain_context(settings.DOMAIN_CONTEXT_DIR)

        # 4. Get LLM client
        llm_client = LLMFactory.get_client(settings.LLM_PROVIDER)

        # 5. Generate SQL
        dialect = db.get_dialect_name()
        response = await llm_client.generate_sql(schema_json, domain_context, task_input, dialect)
        sql_raw = response.content

        # 6. Extract SQL from markdown
        sql_clean = extract_sql_from_markdown(sql_raw)
        if not sql_clean:
            sql_clean = sql_raw.strip()

        logger.info("Generated SQL: %s", sql_clean)

        # 7. Execute SQL
        result = await db.execute_query(sql_clean)

        # 8. Return results
        return json.dumps({"sql": sql_clean, "results": result}, indent=2, default=str)

    except Exception as e:
        logger.exception("Error in handle_user_query")
        return json.dumps({"error": str(e), "sql": sql_clean if sql_clean is not None else None})
    finally:
        if db:
            try:
                await db.disconnect()
            except Exception:
                pass


async def get_db_metadata() -> str:
    """Return database schema metadata + domain context as JSON."""
    db = None
    try:
        db = DatabaseFactory.get_database(settings.DB_TYPE)
        await db.connect()
        schema_metadata = await db.get_schema_metadata()
        domain_context = await load_domain_context(settings.DOMAIN_CONTEXT_DIR)
        return json.dumps({
            "schema": schema_metadata,
            "domain_context": domain_context,
            "dialect": db.get_dialect_name()
        }, indent=2)
    except Exception as e:
        logger.exception("Error in get_db_metadata")
        return json.dumps({"error": str(e)})
    finally:
        if db:
            try:
                await db.disconnect()
            except Exception:
                pass


def extract_sql_from_markdown(text: str) -> str:
    """Extract SQL from markdown code blocks."""
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        raw = match.group(1)
        return raw.strip()
    # Also try generic code block
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        raw = match.group(1)
        return raw.strip()
    return text.strip()
