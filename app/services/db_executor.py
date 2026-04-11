import json
import re
from typing import Union
import psycopg2
import psycopg2.extras
from util.config import settings

async def run_sql_query(query: str) -> str:
    try:
        query = extract_sql_oneline(query)
        print("Running SQL:", query)

        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(query)

        if cur.description:
            result = cur.fetchall()
            output = [dict(row) for row in result]
        else:
            conn.commit()
            output = {"status": "Query executed successfully"}

        cur.close()
        conn.close()
        return json.dumps(output, indent=2)

    except Exception as e:
        print({"error": str(e)})

def extract_sql_oneline(text: str) -> str:
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        raw_sql = match.group(1)
        # Convert escaped newlines and tabs, then flatten
        sql = bytes(raw_sql, "utf-8").decode("unicode_escape")
        return ' '.join(sql.strip().split())
    return text