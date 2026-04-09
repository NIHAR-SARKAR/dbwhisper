from pydantic import BaseModel, Field
from contextlib import AsyncExitStack
import json
from pathlib import Path
from util.config import settings
from services.db_executor import run_sql_query
from services.schema_loader import get_schema_context
from app.services.gpt_handler import OpenAIClient



schema = "authentication"
# -------------------------
# Tools
# -------------------------

async def handle_user_query(task_input: str):
    #  Handles user queries regarding MCP tasks, functions, or data. It processes the input query, interacts with OpenAI to generate SQL based on the provided natural language input, executes the SQL query, and returns the results.
    
    try:
        schema_info = await get_schema_context(schema)
        openAIClient_instance = OpenAIClient()
        sql_to_execute =await openAIClient_instance.generate_sql_from_nl(schema_info,task_input)
        result = await run_sql_query(sql_to_execute)
        raw_text_json = result #here
        print(sql_to_execute)
        print(raw_text_json)
        return raw_text_json                
    except Exception as e:
        print(f"Error: {str(e)}")
        
async def get_db_metadata():
    # Retrieves metadata of the MCP database, including information about available tools and their functions.
    try:
        schema_info = await get_schema_context(schema)
        return schema_info
                
    except Exception as e:
        print(f"Error: {str(e)}")

