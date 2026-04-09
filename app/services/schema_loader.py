from collections import defaultdict
from typing import Dict, List
import psycopg2
import json
from util.config import settings

async def fetch_schema_rows(schema_name: str) -> List[Dict]:
    """Fetch raw column, constraint, and foreign key info from Postgres schema."""
    query = f"""
    SELECT DISTINCT
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
    LEFT JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
        AND tc.table_schema = ccu.table_schema
    WHERE c.table_schema = '{schema_name}'
    ORDER BY c.table_name, c.ordinal_position;
    """
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()
    cur.execute(query, (schema_name,))
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def structure_table_metadata(rows: List[Dict]) -> List[Dict]:
    """Transform raw rows into structured schema context."""
    schema_dict = defaultdict(lambda: {"table": "", "columns": []})

    for row in rows:
        table = row["table_name"]
        schema_name = row["table_schema"]
        full_table_name = f"{schema_name}.{table}"

        column = {
            "name": row["column_name"],
            "type": row["data_type"]
        }

        if row["constraint_type"] == "PRIMARY KEY":
            column["primary_key"] = True
        elif row["constraint_type"] == "FOREIGN KEY":
            column["foreign_key"] = {
                "table": f"{schema_name}.{row['foreign_table_name']}",
                "column": row["foreign_column_name"]
            }

        schema_dict[table]["table"] = full_table_name
        schema_dict[table]["columns"].append(column)

    return list(schema_dict.values())

async def get_schema_context(schema_name: str = 'authentication') -> str:
        """Returns the final JSON schema context string to be used by the LLM."""
        raw_rows = await fetch_schema_rows(schema_name)
        structured = structure_table_metadata(raw_rows)
        return json.dumps(structured, indent=2)

def extract_required_tables(content_list, required_tables):
    filtered_tables = []

    for item in content_list:
        try:
            schema = json.loads(item.text)
            table_name = schema.get("table")
            if table_name in required_tables:
                filtered_tables.append(schema)
        except Exception as e:
            print(f"Skipping invalid JSON: {e}")
    
    return filtered_tables
def extract_foreign_keys(text_contents: List) -> List[Dict]:
    foreign_key_tables = []

    for item in text_contents:
        try:
            table_data = json.loads(item.text)
            table_name = table_data.get("table")
            columns = table_data.get("columns", [])

            # Keep only columns with foreign_key info
            fk_columns = [
                col for col in columns
                if "foreign_key" in col
            ]

            if fk_columns:
                foreign_key_tables.append({
                    "table": table_name,
                    "foreign_keys": fk_columns
                })

        except Exception as e:
            print(f"Skipping invalid JSON: {e}")

    return foreign_key_tables

def extract_relevant_foreign_keys(tables, target_table, target_column):
    result = []

    for table in tables:
        columns = []
        for col in table.get("columns", []):
            fk = col.get("foreign_key")
            if fk and fk["table"] == target_table and fk["column"] == target_column:
                columns.append(col)
            elif col.get("primary_key"):
                columns.append(col)
        
        if columns:
            result.append({"table": table["table"], "columns": columns})

    return result
