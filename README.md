# dbwhisper

<p align="center">
  <img src="DBWhisperLogo.png" alt="Logo" width="300" />
</p>
> **Natural Language → SQL** — A production-grade MCP server that translates plain English into database queries, executes them safely, and returns structured results.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-APACHE-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Protocol-purple.svg)](https://modelcontextprotocol.io)

---

## What is dbwhisper?

**dbwhisper** is a universal database assistant that sits between you and any database. You ask questions in plain English. It generates the SQL, validates it for safety, executes it, and returns clean results.

### Example

```
You: "Show me the top 5 customers by total revenue last month"

SQL: SELECT c.id, c.email, SUM(o.order_total) AS revenue
     FROM public.customers c
     JOIN public.orders o ON c.id = o.customer_id
     WHERE o.created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
     AND o.status = 'completed'
     GROUP BY c.id, c.email
     ORDER BY revenue DESC
     LIMIT 5

Results: [{"id": 101, "email": "alice@example.com", "revenue": 15420.50}, ...]
```

---

## Key Features

### 🔌 Multi-Database Support

Connect to any major database without changing your workflow:

| Database             | Driver      | Status              |
| -------------------- | ----------- | ------------------- |
| PostgreSQL           | `asyncpg`   | ✅ Production-ready |
| MySQL                | `aiomysql`  | ✅ Production-ready |
| Microsoft SQL Server | `aioodbc`   | ✅ Production-ready |
| SQLite               | `aiosqlite` | ✅ Production-ready |
| Oracle               | `oracledb`  | ✅ Production-ready |

Switch databases by changing one environment variable: `DB_TYPE=mysql`

### 🤖 Multi-LLM Provider Support

Use any AI provider — or configure a fallback for resilience:

| Provider                    | Models                                                     | Config Key |
| --------------------------- | ---------------------------------------------------------- | ---------- |
| **OpenAI**                  | GPT-4o, GPT-4-turbo, GPT-4o-mini                           | `openai`   |
| **Azure OpenAI / Azure AI** | GPT-4/5, o1/o3, DeepSeek, Llama, Mistral, + any deployment | `azure`    |
| **Claude (Anthropic)**      | Claude 3.5 Sonnet, Opus, Haiku                             | `claude`   |
| **Kimi (Moonshot AI)**      | moonshot-v1-8k, -32k, -128k                                | `kimi`     |
| **AWS Bedrock**             | Claude, Llama, Cohere, Titan                               | `bedrock`  |

**Azure AI supports ANY deployment ID** — no hardcoded model lists. Pass `gpt-4o-deployment`, `Meta-Llama-3-70B`, `DeepSeek-R1`, or any custom name directly.

### 💰 Token & Cost Optimization

| Feature              | Savings                                                                        |
| -------------------- | ------------------------------------------------------------------------------ |
| **Schema RAG**       | Sends only relevant tables (5 vs 100) → **~95% token reduction**               |
| **SQL Cache**        | Reuses generated SQL for repeated questions → **~50% LLM cost reduction**      |
| **Schema Cache**     | Introspects DB once per hour, not every request → **~90% DB load reduction**   |
| **Connection Pools** | Warm connections eliminate per-request overhead → **~100ms latency reduction** |

### 🛡️ Safety & Validation

- **AST Validation** — Blocks `DROP`, `TRUNCATE`, `DELETE` without `WHERE`
- **EXPLAIN Cost Check** — Rejects queries that would cost too much to run
- **Auto-LIMIT Injection** — Every `SELECT` automatically capped at 100 rows (configurable)
- **Parameterized Queries** — All schema introspection uses binds (`$1`, `%s`, `?`, `:name`)
- **Error Sanitization** — Stack traces stay server-side; clients get clean JSON

### 🔁 Resilience

- **Circuit Breaker** — After 5 LLM failures, auto-switches to fallback provider
- **Graceful Degradation** — Every failure returns structured JSON, never crashes the server
- **Structured Metrics** — Every request logs tokens, latency, cache hits, and costs

### 📝 Domain Context

Load business rules from Markdown files in a `context/` folder. The system automatically injects only the rules relevant to each query.

```markdown
<!-- context/business_rules.md -->

## Active Records

- A user is active if `users.status = 'active'` AND `users.end_date IS NULL`.

## Revenue

Revenue = SUM(order_total) where order_status = 'completed'.
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/NIHAR-SARKAR/dbwhisper.git
cd dbwhisper
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your database and LLM credentials
```

Minimum configuration:

```bash
# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o

# Database
DB_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
```

### 3. Add Domain Context (Optional)

```bash
mkdir -p context
echo "# Business Rules

Only active users have status='active'." > context/business_rules.md
```

### 4. Run

```bash
python app/run_mcp.py
```

Server starts on `http://0.0.0.0:3004` by default.

### 5. Query

Use any MCP client (Claude Desktop, Cursor, Inspector, or HTTP):

```bash
# Using MCP Inspector
npx @modelcontextprotocol/inspector node build/index.js

# Or HTTP directly
curl -X POST http://localhost:3004/tools/handle_user_query   -H "Content-Type: application/json"   -d '{"task_input": "Show me top 5 customers by revenue"}'
```

---

## Response Format

Every query returns structured JSON:

```json
{
  "sql": "SELECT ... LIMIT 100",
  "results": [{ "id": 1, "email": "alice@example.com", "revenue": 15420.5 }],
  "meta": {
    "row_count": 1,
    "returned": 1,
    "has_more": false,
    "execution_time_ms": 12.4,
    "schema_tables_total": 87,
    "schema_tables_selected": 4,
    "schema_cache_hit": true,
    "sql_cache_hit": false,
    "llm_provider": "openai",
    "dialect": "postgresql"
  }
}
```

---

## Architecture

dbwhisper uses a **composable pipeline** with 10 stages:

```
Connect DB → Load Schema → Select Schema (RAG) → Load Domain Context (RAG)
    → Check SQL Cache → Generate SQL (LLM) → Validate SQL (AST + EXPLAIN)
    → Execute SQL → Format Output → Disconnect
```

Each stage is independently testable and replaceable. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full technical deep dive.

---

## Configuration

### Environment Variables

| Variable                    | Required | Default         | Description                                                  |
| --------------------------- | -------- | --------------- | ------------------------------------------------------------ |
| `LLM_PROVIDER`              | No       | `azure`         | LLM provider: `openai`, `azure`, `claude`, `kimi`, `bedrock` |
| `LLM_PROVIDER_FALLBACK`     | No       | `""`            | Backup provider on failure                                   |
| `DB_TYPE`                   | No       | `postgresql`    | Database: `postgresql`, `mysql`, `mssql`, `sqlite`, `oracle` |
| `DATABASE_URL`              | No       | `""`            | Full connection string (overrides discrete params)           |
| `DB_HOST`                   | No       | `localhost`     | Database host                                                |
| `DB_PORT`                   | No       | `5432`          | Database port                                                |
| `DB_NAME`                   | No       | `""`            | Database name                                                |
| `DB_USER`                   | No       | `""`            | Database user                                                |
| `DB_PASSWORD`               | No       | `""`            | Database password                                            |
| `DB_SCHEMA`                 | No       | `public`        | Schema/owner for introspection                               |
| `SQLITE_DB_PATH`            | No       | `./data/app.db` | SQLite file path                                             |
| `DOMAIN_CONTEXT_DIR`        | No       | `./context`     | Markdown context files directory                             |
| `MCP_SERVER_HOST`           | No       | `0.0.0.0`       | Server bind address                                          |
| `MCP_SERVER_PORT`           | No       | `3004`          | Server port                                                  |
| `SCHEMA_CACHE_TTL`          | No       | `3600`          | Schema cache lifetime (seconds)                              |
| `SQL_CACHE_ENABLED`         | No       | `true`          | Enable SQL caching                                           |
| `RAG_TOP_K`                 | No       | `5`             | Tables sent to LLM                                           |
| `MAX_RESULT_ROWS`           | No       | `100`           | Auto-injected row limit                                      |
| `EXPLAIN_MAX_COST`          | No       | `100000`        | Query cost threshold                                         |
| `CIRCUIT_BREAKER_THRESHOLD` | No       | `5`             | Failures before fallback                                     |
| `CIRCUIT_BREAKER_TIMEOUT`   | No       | `60`            | Seconds before retrying primary                              |

### Provider-Specific Variables

**OpenAI:**

- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`

**Azure:**

- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_ID`

**Claude:**

- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`

**Kimi:**

- `KIMI_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`

**Bedrock:**

- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID`

---

## Project Structure

```
dbwhisper/
├── app/
│   ├── server.py              # FastMCP server setup
│   ├── run_mcp.py            # Entry point
│   ├── tools.py              # MCP tool handlers
│   ├── core/                 # Pipeline, metrics, circuit breaker, cache
│   ├── services/             # LLM providers, databases, RAG, validation
│   └── util/                 # Configuration
├── context/                  # Domain context Markdown files
├── cache/                    # Runtime cache directory
├── data/                     # SQLite default path
├── .env.example              # Configuration template
├── requirements.txt          # Dependencies
├── README.md                 # This file
├── SETUP.md                  # Detailed setup instructions
└── ARCHITECTURE.md           # Technical architecture deep dive
```

---

## Use Cases

| Scenario             | How dbwhisper Helps                                    |
| -------------------- | ------------------------------------------------------ |
| **BI Dashboards**    | Business users ask questions without learning SQL      |
| **Customer Support** | Agents query order history in natural language         |
| **Data Exploration** | Analysts explore schemas without writing JOINs         |
| **API Backend**      | Embed as an MCP tool in Claude, Cursor, or custom apps |
| **Multi-DB Ops**     | One interface for PostgreSQL, MySQL, Oracle, etc.      |
| **Cost Control**     | Token optimization keeps LLM bills predictable         |

---

## Performance

| Metric                                        | Typical Value |
| --------------------------------------------- | ------------- |
| Cold start (schema cache miss)                | ~800ms        |
| Warm query (schema cache hit, SQL cache miss) | ~150ms        |
| Hot query (all caches hit)                    | ~15ms         |
| Schema introspection (one-time)               | ~50ms         |
| LLM generation (GPT-4o)                       | ~600ms        |
| LLM generation (GPT-4o-mini)                  | ~200ms        |

---

## Security

- No SQL injection: all introspection queries are parameterized
- No arbitrary execution: AST validation blocks dangerous commands
- No data leaks: auto-LIMIT caps results, errors are sanitized
- No credential exposure: all keys via environment variables

See [ARCHITECTURE.md](ARCHITECTURE.md) → Security Model for the full threat matrix.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Install dev dependencies: `pip install -r requirements.txt`
4. Make changes, add tests
5. Submit a pull request

### Adding a New Database

1. Implement `BaseDatabase` in `app/services/databases/mydb.py`
2. Register in `DatabaseFactory`
3. Add introspection query with parameterization
4. Add `explain_query()` method
5. Update `requirements.txt` with driver

### Adding a New LLM Provider

1. Implement `BaseLLMClient` in `app/services/llm_providers/myprovider.py`
2. Register in `LLMFactory`
3. Handle `generate_sql()` with proper error wrapping
4. Update `requirements.txt` with SDK

---

## License

APACHE License — see [LICENSE](LICENSE) for full text.

---

## Support

- 📖 Documentation: [ARCHITECTURE.md](ARCHITECTURE.md)
- 🛠️ Setup Guide: [SETUP.md](SETUP.md)
- 🐛 Issues: [GitHub Issues](https://github.com/NIHAR-SARKAR/dbwhisper/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/NIHAR-SARKAR/dbwhisper/discussions)

---

> **Built with** FastMCP · asyncpg · httpx · sqlparse · python-dotenv
