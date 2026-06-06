# MCP Learning — Universal Database Assistant

A production-ready, extensible MCP (Model Context Protocol) server that translates natural language into SQL, executes it against any supported database, and returns structured results. Built with clean architecture patterns, full async support, and zero hardcoded provider logic.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Supported LLM Providers](#supported-llm-providers)
- [Supported Databases](#supported-databases)
- [Domain Context System](#domain-context-system)
- [Security](#security)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [Error Handling & Resilience](#error-handling--resilience)
- [Backward Compatibility](#backward-compatibility)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

### Multi-LLM Provider Support (Strategy Pattern)
Switch between LLM providers by changing a single environment variable. No code changes required.

| Provider | SDK | Config Key | Notes |
|----------|-----|------------|-------|
| **OpenAI (ChatGPT)** | `openai.AsyncOpenAI` | `openai` | GPT-4o, GPT-4-turbo, etc. |
| **Azure OpenAI / Azure AI** | `openai.AsyncAzureOpenAI` | `azure` | Supports **ANY** deployment ID — GPT-4, GPT-5, o1, o3-mini, Meta-Llama, DeepSeek, Mistral, Cohere, AI21, or custom models. Deployment ID is opaque; passed directly to API. |
| **Claude (Anthropic)** | `anthropic.AsyncAnthropic` | `claude` | Claude 3.5 Sonnet, Claude 3 Opus, etc. |
| **Kimi (Moonshot AI)** | `openai.AsyncOpenAI` with custom `base_url` | `kimi` | moonshot-v1-8k, moonshot-v1-32k, etc. |
| **AWS Bedrock** | `boto3` bedrock-runtime `converse()` | `bedrock` | Unified Converse API. Supports Anthropic, Meta, Cohere, Amazon Titan models. |

- **Temperature locked to 0.1** for deterministic SQL generation across all providers.
- **Usage metadata** (tokens consumed) returned in every response where available.
- **Graceful degradation**: if an LLM provider fails, the error is caught, logged, and returned as JSON — the server never crashes.

### Multi-Database Support (Factory Pattern)
Connect to any of the five major databases. Schema introspection is fully automated and returns a **uniform JSON structure** regardless of backend.

| Database | Driver | Config Key | Schema Introspection Method |
|----------|--------|------------|---------------------------|
| **PostgreSQL** | `psycopg2` | `postgresql` | `information_schema` + `constraint_column_usage` |
| **MySQL** | `PyMySQL` | `mysql` | `information_schema.COLUMNS` + `KEY_COLUMN_USAGE` |
| **Microsoft SQL Server** | `pyodbc` | `mssql` | `INFORMATION_SCHEMA` views |
| **SQLite** | `sqlite3` (built-in) | `sqlite` | `PRAGMA table_info` + `PRAGMA foreign_key_list` |
| **Oracle** | `oracledb` | `oracle` | `ALL_TAB_COLUMNS` + `ALL_CONSTRAINTS` |

- **Connection pooling friendly**: each tool invocation creates and closes its own connection, preventing stale connections.
- **DSN or discrete params**: connect via `DATABASE_URL` or individual `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

### Domain Context / Metadata Injection
Load business rules, definitions, and domain-specific knowledge from Markdown files in a `context/` directory. The content is automatically concatenated and injected into the LLM system prompt **after** schema metadata, giving the model business context without polluting the database.

Example use cases:
- "A user is active only if `status = 'active'` AND `end_date IS NULL`"
- "Revenue = SUM(order_total) where order_status = 'completed'`"
- Custom KPI definitions, approval workflows, or soft-delete policies

If the `context/` directory is missing or empty, the Domain Context section is silently omitted from the prompt.

### Schema Introspection & Unified JSON Format
Every database adapter returns an identical schema representation:

```json
[
  {
    "table": "public.users",
    "columns": [
      {"name": "id", "type": "integer", "primary_key": true},
      {"name": "email", "type": "varchar"},
      {"name": "org_id", "type": "integer", "foreign_key": {"table": "public.organizations", "column": "id"}}
    ]
  }
]
```

This uniform format means the LLM prompt construction is provider-agnostic and database-agnostic.

---

## Architecture

### Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Strategy Pattern** | `app/services/llm_providers/` | Swap LLM providers at runtime via `LLMFactory` |
| **Factory Pattern** | `app/services/databases/` | Swap database adapters at runtime via `DatabaseFactory` |
| **Template Method** | `BaseLLMClient._build_prompt()` | Shared prompt construction across all providers |
| **Adapter Pattern** | Each database class | Normalize disparate DB metadata APIs into one JSON schema |

### Data Flow

```
User Query (natural language)
        ↓
   MCP Tool: handle_user_query()
        ↓
   DatabaseFactory.get_database(DB_TYPE)
        ↓
   db.connect() → db.get_schema_metadata()
        ↓
   load_domain_context(DOMAIN_CONTEXT_DIR)
        ↓
   LLMFactory.get_client(LLM_PROVIDER)
        ↓
   llm.generate_sql(schema, domain, query, dialect)
        ↓
   extract_sql_from_markdown(response)
        ↓
   db.execute_query(sql)
        ↓
   JSON: { "sql": "...", "results": [...] }
```

### Async-First
All database and LLM operations are `async`. The server uses `asyncio` event loops compatible with FastMCP's HTTP transport.

---

## Supported LLM Providers

### OpenAI
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
# Optional: OPENAI_BASE_URL=https://api.openai.com/v1
```

### Azure OpenAI / Azure AI Foundry
```bash
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_ID=your-deployment-name
```
**Critical**: `AZURE_OPENAI_DEPLOYMENT_ID` is **opaque**. It can be:
- `gpt-4o-deployment`
- `Meta-Llama-3-70B`
- `DeepSeek-R1`
- `my-custom-model`

The code passes it directly to `AsyncAzureOpenAI.chat.completions.create(model=...)`. No validation, no hardcoded model lists.

### Kimi (Moonshot AI)
```bash
LLM_PROVIDER=kimi
KIMI_API_KEY=sk-...
KIMI_MODEL=moonshot-v1-8k
# Optional: KIMI_BASE_URL=https://api.moonshot.cn/v1
```

### Claude (Anthropic)
```bash
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### AWS Bedrock
```bash
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```
Uses the modern `boto3.client("bedrock-runtime").converse()` unified API.

---

## Supported Databases

### PostgreSQL
```bash
DB_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
# OR
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dbname
DB_USER=user
DB_PASSWORD=pass
DB_SCHEMA=public
```

### MySQL
```bash
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=dbname
DB_USER=user
DB_PASSWORD=pass
DB_SCHEMA=dbname
```

### Microsoft SQL Server
```bash
DB_TYPE=mssql
DB_HOST=localhost
DB_PORT=1433
DB_NAME=dbname
DB_USER=sa
DB_PASSWORD=YourPassword123
DB_SCHEMA=dbo
```
Requires ODBC Driver 17 for SQL Server installed on the host.

### SQLite
```bash
DB_TYPE=sqlite
SQLITE_DB_PATH=./data.db
```
No additional drivers required. Schema introspection uses `PRAGMA` commands.

### Oracle
```bash
DB_TYPE=oracle
DB_HOST=localhost
DB_PORT=1521
DB_NAME=ORCLPDB1
DB_USER=system
DB_PASSWORD=pass
DB_SCHEMA=SYSTEM
```

---

## Domain Context System

Create a `context/` directory in the project root and add `.md` files:

```markdown
<!-- context/business_rules.md -->
# Business Rules

## Active Records
- A user is considered active if `users.status = 'active'` AND `users.end_date IS NULL`.
- Always filter for active users unless the user explicitly asks for inactive or all users.

## Currency
- All monetary amounts in the `orders` table are stored in USD.
```

```markdown
<!-- context/definitions.md -->
# Domain Definitions

## Revenue
Revenue = SUM(order_total) where order_status = 'completed' and payment_status = 'paid'.

## Churned User
A user is churned if they have not placed an order in the last 90 days.
```

These files are concatenated in alphabetical order and injected into the LLM system prompt under a `Domain Context:` section. This keeps business logic out of the database schema while still guiding the model's SQL generation.

---

## Security

- **Parameterized Schema Queries**: All `information_schema` / `ALL_TAB_COLUMNS` / `PRAGMA` queries use parameterized placeholders (`%s`, `?`, `:schema_name`) instead of f-string interpolation. This prevents SQL injection even during schema introspection.
- **No Hardcoded Secrets**: All credentials come from environment variables via `python-dotenv`.
- **Error Sanitization**: Database connection errors and LLM API errors are caught and returned as JSON strings. Stack traces are logged server-side but never leaked to the client.
- **No Arbitrary SQL Execution Without LLM**: The `handle_user_query` tool always generates SQL through the LLM first; there is no direct raw-SQL tool exposed to the MCP client.

---

## Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/NIHAR-SARKAR/mcp-learning.git
cd mcp-learning
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your LLM provider and database credentials
```

### 3. Add Domain Context (Optional)
```bash
mkdir -p context
echo "# Business Rules\n\nAlways filter active users." > context/business_rules.md
```

### 4. Run the Server
```bash
python app/run_mcp.py
```

The server starts on `http://0.0.0.0:3004` by default (configurable via `MCP_SERVER_HOST` and `MCP_SERVER_PORT`).

### 5. Test with an MCP Client
Use any MCP-compatible client (e.g., Claude Desktop, a custom HTTP client, or the MCP Inspector) to call:

- **`handle_user_query`** — pass a natural language query, receive `{sql, results}` JSON.
- **`get_db_metadata`** — receive the full database schema + domain context + dialect as JSON.

---

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `azure` | LLM provider: `openai`, `azure`, `claude`, `kimi`, `bedrock` |
| `DB_TYPE` | No | `postgresql` | Database: `postgresql`, `mysql`, `mssql`, `sqlite`, `oracle` |
| `DATABASE_URL` | No | `""` | Full connection string (overrides discrete params if set) |
| `DB_HOST` | No | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `DB_NAME` | No | `""` | Database name |
| `DB_USER` | No | `""` | Database user |
| `DB_PASSWORD` | No | `""` | Database password |
| `DB_SCHEMA` | No | `public` | Schema/owner for introspection |
| `SQLITE_DB_PATH` | No | `./database.db` | Path to SQLite file |
| `DOMAIN_CONTEXT_DIR` | No | `./context` | Directory containing `.md` context files |
| `MCP_SERVER_HOST` | No | `0.0.0.0` | HTTP server bind address |
| `MCP_SERVER_PORT` | No | `3004` | HTTP server port |

### Provider-Specific Variables

| Provider | Variables |
|----------|-----------|
| OpenAI | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| Azure | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_ID` |
| Kimi | `KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL` |
| Claude | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| Bedrock | `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID` |

---

## Usage Examples

### Example 1: Natural Language to SQL
**Input:**
```json
{
  "task_input": "Show me the top 5 active users by total order amount"
}
```

**Output:**
```json
{
  "sql": "SELECT u.id, u.email, SUM(o.order_total) AS total_spent FROM public.users u JOIN public.orders o ON u.id = o.user_id WHERE u.status = 'active' AND u.end_date IS NULL GROUP BY u.id, u.email ORDER BY total_spent DESC LIMIT 5",
  "results": [
    {"id": 101, "email": "alice@example.com", "total_spent": 15420.50},
    {"id": 42, "email": "bob@example.com", "total_spent": 12300.00}
  ]
}
```

### Example 2: Get Database Metadata
**Input:** (no parameters)

**Output:**
```json
{
  "schema": [
    {
      "table": "public.users",
      "columns": [
        {"name": "id", "type": "integer", "primary_key": true},
        {"name": "email", "type": "varchar"}
      ]
    }
  ],
  "domain_context": "=== File: business_rules.md ===\n# Business Rules\n...",
  "dialect": "postgresql"
}
```

---

## Project Structure

```
mcp-learning/
├── app/
│   ├── __init__.py
│   ├── server.py                 # FastMCP server setup
│   ├── run_mcp.py                # Entry point: logging + server start
│   ├── tools.py                  # MCP tools: handle_user_query, get_db_metadata
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_factory.py      # Routes LLM_PROVIDER → provider class
│   │   ├── db_factory.py       # Routes DB_TYPE → database class
│   │   ├── domain_context.py   # Loads and concatenates .md context files
│   │   ├── schema_loader.py    # Legacy wrapper (delegates to factory)
│   │   ├── db_executor.py      # Legacy wrapper (delegates to factory)
│   │   ├── llm_providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # BaseLLMClient abstract class + LLMResponse dataclass
│   │   │   ├── openai_provider.py
│   │   │   ├── azure_provider.py
│   │   │   ├── claude_provider.py
│   │   │   ├── kimi_provider.py
│   │   │   └── bedrock_provider.py
│   │   └── databases/
│   │       ├── __init__.py
│   │       ├── base.py         # BaseDatabase abstract class
│   │       ├── postgres.py     # psycopg2 adapter
│   │       ├── mysql.py        # PyMySQL adapter
│   │       ├── mssql.py        # pyodbc adapter
│   │       ├── sqlite.py       # sqlite3 adapter
│   │       └── oracle.py       # oracledb adapter
│   └── util/
│       ├── __init__.py
│       └── config.py           # Settings dataclass + legacy property mappings
├── context/
│   ├── business_rules.md       # Example domain context
│   └── definitions.md          # Example domain context
├── .env.example                # Template environment file
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Error Handling & Resilience

| Failure Scenario | Behavior |
|------------------|----------|
| LLM API timeout / rate limit | Caught, logged, returns `{"error": "LLM generation failed: ...", "sql": null}` |
| Database connection refused | Caught, logged, returns `{"error": "Database error: ..."}` |
| Invalid SQL generated | Caught at execution time, returns `{"error": "Database error: ...", "sql": "..."}` |
| Missing `.env` | Falls back to defaults (Azure + PostgreSQL + localhost) |
| Empty `context/` directory | Domain context omitted from prompt; server continues normally |
| Unsupported `LLM_PROVIDER` | `ValueError` raised at factory time with list of supported providers |
| Unsupported `DB_TYPE` | `ValueError` raised at factory time with list of supported databases |

All errors are **non-fatal** to the MCP server process. The HTTP transport stays alive.

---

## Backward Compatibility

If you are upgrading from the previous version of this project, old environment variables still work:

| Old Variable | Maps To |
|--------------|---------|
| `MODEL_URL` | `AZURE_OPENAI_ENDPOINT` |
| `MODEL_API_KEY` | `AZURE_OPENAI_API_KEY` |
| `MODEL_API_VERSION` | `AZURE_OPENAI_API_VERSION` |
| `MODEL_NAME` | `AZURE_OPENAI_DEPLOYMENT_ID` |

These are exposed as `@property` methods on the `Settings` class. If the new variables are not set but the old ones are, the old values are used automatically.

---

## Troubleshooting

### "Module not found" errors
Ensure you installed all extras:
```bash
pip install -r requirements.txt
```
If you only need PostgreSQL + OpenAI, you can skip `pyodbc`, `oracledb`, etc., but the factory will raise an error if you later try to use them.

### "ODBC Driver 17 for SQL Server not found" (MSSQL)
Install the Microsoft ODBC driver for your OS:
- **Ubuntu/Debian**: `sudo apt-get install unixodbc unixodbc-dev msodbcsql17`
- **macOS**: `brew install microsoft-openjdk msodbcsql17 mssql-tools`
- **Windows**: Download from Microsoft website.

### Oracle "ORA-12541: TNS:no listener"
Verify `DB_HOST` and `DB_PORT` point to a running Oracle listener. For Oracle XE, the default service name is often `XEPDB1`.

### Azure "Deployment not found"
Double-check `AZURE_OPENAI_DEPLOYMENT_ID` exactly matches the deployment name in your Azure OpenAI / Azure AI Foundry portal. It is case-sensitive.

### Claude "max_tokens required"
The Claude provider sets `max_tokens=4000` by default. If you need more, edit `app/services/llm_providers/claude_provider.py`.

---

## License

MIT License — see repository for full text.

---

## Contributing

1. Add a new LLM provider: implement `BaseLLMClient` in `app/services/llm_providers/`, register in `LLMFactory`.
2. Add a new database: implement `BaseDatabase` in `app/services/databases/`, register in `DatabaseFactory`.
3. Ensure schema JSON output matches the unified format.
4. Use `logging`, not `print`.
5. Parameterize all schema queries.
