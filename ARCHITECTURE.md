# dbwhisper — Architecture Overview

> **Version:** v2.0  
> **Last Updated:** 2026-06-06  
> **Repository:** `dbwhisper`  
> **Purpose:** Production-grade natural language → SQL translation engine with multi-database, multi-LLM, and cost-optimized execution.

---

## Table of Contents

- [High-Level Flow](#high-level-flow)
- [Design Philosophy](#design-philosophy)
- [Layered Architecture](#layered-architecture)
- [Pipeline Deep Dive](#pipeline-deep-dive)
- [Data Flow Diagram](#data-flow-diagram)
- [Component Reference](#component-reference)
- [Request Lifecycle](#request-lifecycle)
- [Error Handling & Resilience](#error-handling--resilience)
- [Caching Strategy](#caching-strategy)
- [Security Model](#security-model)
- [Scaling Considerations](#scaling-considerations)
- [Technology Stack](#technology-stack)
- [Directory Structure](#directory-structure)
- [Configuration Reference](#configuration-reference)
- [Glossary](#glossary)

---

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              MCP CLIENT                                  │
│         (Claude Desktop, Cursor, Inspector, HTTP client)                │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTP / stdio
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTMCP SERVER                                   │
│  ┌──────────────┐  ┌──────────────┐                                    │
│  │ handle_user  │  │ get_db_      │                                    │
│  │ _query()     │  │ metadata()   │                                    │
│  └──────┬───────┘  └──────────────┘                                    │
│         │                                                                │
│         ▼                                                                │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │              PIPELINERUNNER (10 Stages)                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │ Connect │→│ Load    │→│ Select  │→│ Load    │→│ Check   │    │   │
│  │  │ DB      │  │ Schema  │  │ Schema  │  │ Domain  │  │ SQL     │    │   │
│  │  │ Pool    │  │ Cache   │  │ RAG     │  │ Context │  │ Cache   │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  │         ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │   │
│  │    ┌────┤ Generate│→│ Validate│→│ Execute │→│ Format  │────┐   │   │
│  │    │    │ SQL     │  │ SQL     │  │ SQL     │  │ Output  │    │   │
│  │    │    └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │   │
│  │    │    ┌─────────┐                                         │   │   │
│  │    └────┤Fallback │←── Circuit Breaker (on LLM failure)      │   │   │
│  │         │ LLM     │                                         │   │   │
│  │         └─────────┘                                         │   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│         │                                                                │
│         ▼                                                                │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │              STRUCTURED JSON RESPONSE                            │   │
│  │  { sql, results, meta: { row_count, execution_time_ms, ... } }   │   │
│  └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Design Philosophy

| Principle | Implementation |
|-----------|---------------|
| **Token Efficiency** | Schema RAG sends only relevant tables (5 vs 100). Domain Context RAG sends only relevant rules. |
| **Cost Reduction** | SQL cache eliminates redundant LLM calls. Schema cache eliminates redundant DB introspection. |
| **Safety First** | AST validation blocks dangerous commands. EXPLAIN cost check prevents runaway queries. Auto-LIMIT caps result size. |
| **Resilience** | Circuit breaker auto-fails to backup LLM. Graceful degradation at every stage. |
| **Observability** | Every request emits structured metrics (tokens, latency, cache hits, costs). |
| **Extensibility** | Pipeline stages are composable. New DB or LLM = one file + factory registration. |
| **Zero Vendor Lock-in** | httpx-based Azure provider. No SDK dependency for any provider. |

---

## Layered Architecture

```
┌────────────────────────────────────────┐
│  Layer 4: Presentation (MCP Protocol)  │
│  server.py, tools.py                   │
│  FastMCP HTTP/stdio transport          │
├────────────────────────────────────────┤
│  Layer 3: Orchestration (Pipeline)     │
│  pipeline.py, pipeline_stages.py       │
│  Composable stage runner, metrics      │
├────────────────────────────────────────┤
│  Layer 2: Business Logic               │
│  schema_rag.py, sql_validator.py       │
│  sql_cache.py, domain_context.py       │
│  circuit_breaker.py, cache.py        │
├────────────────────────────────────────┤
│  Layer 1: Adapters (Strategy/Factory)  │
│  llm_providers/, databases/            │
│  llm_factory.py, db_factory.py       │
├────────────────────────────────────────┤
│  Layer 0: Infrastructure             │
│  config.py, metrics.py                 │
│  Environment, logging, observability   │
└────────────────────────────────────────┘
```

---

## Pipeline Deep Dive

### Stage 1: ConnectDatabaseStage
```
DatabaseFactory.get_database(DB_TYPE) → async pool creation
```
- **PostgreSQL:** `asyncpg.create_pool(min=2, max=10)`
- **MySQL:** `aiomysql.create_pool(min=2, max=10)`
- **MSSQL:** `aioodbc.create_pool(min=2, max=10)`
- **SQLite:** `aiosqlite.connect()` (single connection)
- **Oracle:** `oracledb.create_pool(min=2, max=10)`

**Why pool?** Eliminates ~100ms connect/disconnect overhead per request. Supports concurrent MCP clients.

---

### Stage 2: LoadSchemaStage
```
Cache check → Cache hit? Return cached schema
              Cache miss? Run introspection query → Write to disk cache
```

**Introspection queries per database:**

| DB | Tables | Method | Parameterization |
|----|--------|--------|-------------------|
| PostgreSQL | `information_schema` | JOIN columns + constraints | `$1` (asyncpg) |
| MySQL | `information_schema` | JOIN COLUMNS + KEY_COLUMN_USAGE | `%s` (aiomysql) |
| MSSQL | `INFORMATION_SCHEMA` | JOIN COLUMNS + TABLE_CONSTRAINTS | `?` (aioodbc) |
| SQLite | `sqlite_master` | `PRAGMA table_info` + `PRAGMA foreign_key_list` | N/A |
| Oracle | `ALL_TAB_COLUMNS` | JOIN ALL_CONSTRAINTS + ALL_CONS_COLUMNS | `:schema_name` |

**Cache key:** `md5(db_type + schema_name)`  
**Cache location:** `cache/schema_<hash>.json`  
**TTL:** `SCHEMA_CACHE_TTL` (default 3600s)

---

### Stage 3: SelectSchemaStage (Schema RAG)

**Problem:** Sending 100 tables × 20 columns = ~30,000 tokens to LLM. Expensive and slow.

**Solution:** Keyword-based retrieval + FK graph expansion.

```
User query: "Show me top 5 churned users last month"
    ↓
Tokenize: {"show", "top", "churned", "users", "last", "month"}
    ↓
Score every table:
  users       → 10.0 (table name match) + 3.0 (column "status") + 1.0 ("email") = 14.0
  orders      → 3.0 (column "user_id") + 1.0 ("total") = 4.0
  subscriptions → 1.0 ("end_date") = 1.0
    ↓
Top-K (default 5): [users, orders, subscriptions, ...]
    ↓
FK Expansion:
  users.org_id → FK to organizations → ADD organizations table
  orders.product_id → FK to products → ADD products table
    ↓
Final selected tables: [users, orders, subscriptions, organizations, products]
```

**Token reduction:** 30,000 → ~800 tokens (95% savings on large schemas)

---

### Stage 4: LoadDomainContextStage

**Problem:** `business_rules.md` + `definitions.md` can be 5,000 tokens. Irrelevant for most queries.

**Solution:** Chunk by Markdown headers, score by keyword overlap, return top-3 relevant chunks.

```
Query: "What is monthly revenue?"
Chunks:
  "# Revenue
Revenue = SUM..."                → score 3 ("revenue" × 2 + "monthly" × 1)
  "# Churned User
A user is churned..."        → score 0
  "# Active Records
A user is active..."       → score 0
    ↓
Return: [Revenue chunk only]
```

**Fallback:** If RAG returns nothing, fall back to full concatenation.

---

### Stage 5: CheckSQLCacheStage

**Exact-match cache:** `md5(schema_hash + query_hash)` → stored SQL

**Hit scenario:**
```
User 1: "Show top 5 customers by revenue"
  → Cache miss → LLM generates SQL → Cache writes result
User 2 (1 hour later): "Show top 5 customers by revenue"
  → Cache hit → Skip LLM entirely → Instant response
```

**Storage:** `cache/sql_<hash>.json`  
**Lifetime:** Persistent (no TTL — SQL doesn't change for same schema + query)

---

### Stage 6: GenerateSQLStage

**Primary path:**
```
LLMFactory.get_client(LLM_PROVIDER)
  → BaseLLMClient._build_prompt(schema, domain, dialect)
  → Provider-specific API call
  → LLMResponse(content, model, usage)
```

**Azure provider (httpx-based):**
```
1. Detect model family from deployment name (gpt-5.1, o3, deepseek, llama, ...)
2. Resolve API pattern (Legacy / V1 / Responses / AI Foundry)
3. Build URL: /openai/deployments/{name}/chat/completions?api-version=...
4. Build request body:
   - Chat Completions: { messages, model, temperature, max_tokens }
   - Responses API: { input, model, max_output_tokens } (NO temperature)
5. POST via httpx.AsyncClient
6. Parse response (choices[0].message.content or output_text)
```

**Circuit breaker wrapping:**
```
CircuitBreakerRegistry.get("azure")
  → Track failures
  → Trip after 5 failures → Open state for 60s
  → On next request: Try fallback provider (OpenAI, Claude, etc.)
```

---

### Stage 7: ValidateSQLStage

**Two-phase validation:**

#### Phase A: AST Static Analysis (sqlparse)
```python
parsed = sqlparse.parse(sql)
first_token = parsed[0].get_type()

# Block dangerous commands
tokens = {t.lower() for t in parsed[0].flatten()}
if tokens & {"drop", "truncate", "alter", "grant", "revoke", "create"}:
    REJECT

# DELETE/UPDATE without WHERE
if first_token in ("DELETE", "UPDATE") and "WHERE" not in tokens:
    REJECT

# Warn on SELECT *
if "select *" in sql.lower():
    WARN: "Consider specifying columns"
```

#### Phase B: EXPLAIN Cost Check
```python
plan = await db.explain_query(sql)
cost = extract_cost(plan)  # PostgreSQL: Plan.Total Cost

if cost > EXPLAIN_MAX_COST (default 100,000):
    REJECT: "Query cost exceeds threshold"
```

**Per-database EXPLAIN:**

| DB | EXPLAIN Method | Cost Field |
|----|---------------|------------|
| PostgreSQL | `EXPLAIN (FORMAT JSON)` | `Plan.Total Cost` |
| MySQL | `EXPLAIN FORMAT=JSON` | `query_block.cost_info.query_cost` |
| MSSQL | `SET SHOWPLAN_XML ON` | XML parsing (not implemented) |
| SQLite | `EXPLAIN QUERY PLAN` | No cost — row count estimate |
| Oracle | `EXPLAIN PLAN` + `DBMS_XPLAN` | Plan table output |

---

### Stage 8: ExecuteSQLStage

**Auto-LIMIT injection:**
```python
if sql starts with "SELECT" and "LIMIT" not in sql:
    sql = f"{sql} LIMIT {MAX_RESULT_ROWS}"  # default 100
```

**Per-database LIMIT syntax:**

| DB | Injected Syntax |
|----|----------------|
| PostgreSQL | `LIMIT 100` |
| MySQL | `LIMIT 100` |
| MSSQL | `SELECT TOP 100 ...` |
| SQLite | `LIMIT 100` |
| Oracle | `FETCH FIRST 100 ROWS ONLY` |

**Execution via pool:**
```python
async with pool.acquire() as conn:
    rows = await conn.fetch(sql)  # asyncpg
    return [dict(r) for r in rows]
```

---

### Stage 9: FormatOutputStage

**Structured response:**
```json
{
  "sql": "SELECT u.id, u.email, SUM(o.total) ... LIMIT 100",
  "results": [
    {"id": 101, "email": "alice@example.com", "sum": 15420.50},
    {"id": 42, "email": "bob@example.com", "sum": 12300.00}
  ],
  "meta": {
    "row_count": 2,
    "returned": 2,
    "has_more": false,
    "execution_time_ms": 12.4,
    "schema_tables_total": 87,
    "schema_tables_selected": 4,
    "schema_cache_hit": true,
    "sql_cache_hit": false,
    "llm_provider": "azure",
    "dialect": "postgresql"
  }
}
```

---

### Stage 10: DisconnectDatabaseStage

```python
await pool.close()  # Graceful pool shutdown
```

**Note:** In production with long-running server, pools stay warm. Disconnect happens on server shutdown or error recovery.

---

## Data Flow Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   USER      │────→│  NATURAL    │────→│   SCHEMA    │
│   QUERY     │     │  LANGUAGE   │     │    RAG      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   RESULTS   │←────│   EXECUTE   │←────│  VALIDATE   │
│   + META    │     │    SQL      │     │    SQL      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                                ▼
                                       ┌─────────────┐
                                       │   GENERATE  │
                                       │    SQL      │
                                       │  (LLM/Cache)│
                                       └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   DOMAIN    │
                                       │   CONTEXT   │
                                       │   (RAG)     │
                                       └─────────────┘
```

---

## Component Reference

### Core Framework

| File | Role | Pattern |
|------|------|---------|
| `pipeline.py` | Stage interface + runner | Template Method |
| `metrics.py` | Request telemetry | Observer |
| `circuit_breaker.py` | Failure isolation | Circuit Breaker |
| `cache.py` | Schema disk cache | Cache-Aside |

### Business Logic

| File | Role | Pattern |
|------|------|---------|
| `schema_rag.py` | Table selection | Retrieval-Augmented Generation |
| `domain_context.py` | Rule loading + RAG | Content-Based Retrieval |
| `sql_validator.py` | SQL safety | Validator Chain |
| `sql_cache.py` | Generated SQL cache | Key-Value Cache |

### Adapters

| File | Role | Pattern |
|------|------|---------|
| `llm_factory.py` | Provider routing | Factory + Strategy |
| `db_factory.py` | Database routing | Factory |
| `azure_provider.py` | Azure httpx client | Adapter |
| `postgres.py` | PostgreSQL async | Adapter |
| `mysql.py` | MySQL async | Adapter |

---

## Request Lifecycle

### Happy Path (Cache Hit, No LLM)

```
T+0ms    Request received
T+1ms    ConnectDatabaseStage → pool acquired (warm)
T+2ms    LoadSchemaStage → cache hit (disk read)
T+3ms    SelectSchemaStage → RAG selects 4 tables
T+4ms    LoadDomainContextStage → RAG selects 1 rule
T+5ms    CheckSQLCacheStage → HIT! Return cached SQL
T+6ms    ValidateSQLStage → AST pass, EXPLAIN pass
T+8ms    ExecuteSQLStage → pool query, LIMIT 100
T+10ms   FormatOutputStage → JSON response
T+12ms   Total response time
```

### Cold Path (Cache Miss, LLM Call)

```
T+0ms    Request received
T+1ms    ConnectDatabaseStage → pool acquired
T+2ms    LoadSchemaStage → cache miss → introspect DB (50ms)
T+52ms   SelectSchemaStage → RAG selects 4 tables
T+53ms   LoadDomainContextStage → RAG selects 1 rule
T+54ms   CheckSQLCacheStage → MISS
T+55ms   GenerateSQLStage → LLM API call (800ms)
T+855ms  ValidateSQLStage → AST pass, EXPLAIN pass (5ms)
T+860ms  ExecuteSQLStage → pool query (10ms)
T+870ms  FormatOutputStage → JSON response
T+872ms  Total response time
```

### Failure Path (Circuit Breaker)

```
T+0ms    Request received
T+1ms    ConnectDatabaseStage → pool acquired
T+2ms    LoadSchemaStage → cache hit
T+3ms    SelectSchemaStage → RAG selects tables
T+4ms    LoadDomainContextStage → RAG selects rules
T+5ms    CheckSQLCacheStage → MISS
T+6ms    GenerateSQLStage → Azure API call → TIMEOUT
T+126ms  Retry 1 → TIMEOUT
T+246ms  Retry 2 → TIMEOUT
T+366ms  Retry 3 → TIMEOUT
T+486ms  Retry 4 → TIMEOUT
T+606ms  Retry 5 → TIMEOUT
T+606ms  Circuit breaker TRIPS (Azure → OPEN)
T+607ms  Fallback to OpenAI provider
T+607ms  OpenAI API call (600ms)
T+1207ms ValidateSQLStage → pass
T+1215ms ExecuteSQLStage → query
T+1220ms FormatOutputStage → JSON response
T+1222ms Total response time (with fallback)
```

---

## Error Handling & Resilience

| Failure Point | Handler | Recovery |
|---------------|---------|----------|
| DB connection refused | Exception caught | Return error JSON, pool retry on next request |
| Schema introspection fails | Exception caught | Return cached schema if available, else error |
| LLM API timeout (×5) | Circuit breaker trips | Auto-fallback to backup provider |
| All LLM providers fail | Exception caught | Return error JSON with details |
| SQL validation fails | REJECT stage | Return error with `sql` field for debugging |
| EXPLAIN cost exceeded | REJECT stage | Suggest user refine query |
| Query execution fails | Exception caught | Return error JSON with SQL for debugging |
| Result serialization fails | Exception caught | Return error JSON |

**Guarantee:** The MCP server process never crashes. Every error is caught, logged, and returned as structured JSON.

---

## Caching Strategy

### Three-Tier Cache

```
┌─────────────────────────────────────────────┐
│  Tier 1: SQL Cache (Exact Match)            │
│  Key: md5(schema_hash + query_hash)           │
│  Hit: Skip LLM entirely                       │
│  TTL: Infinite (SQL is deterministic)         │
│  Storage: cache/sql_*.json                     │
├─────────────────────────────────────────────┤
│  Tier 2: Schema Cache (DB Introspection)    │
│  Key: md5(db_type + schema_name)              │
│  Hit: Skip DB introspection                   │
│  TTL: SCHEMA_CACHE_TTL (default 3600s)      │
│  Storage: cache/schema_*.json                │
├─────────────────────────────────────────────┤
│  Tier 3: Connection Pool (Warm Connections)   │
│  Hit: Skip TCP handshake + auth               │
│  TTL: Process lifetime                        │
│  Storage: In-memory async pool                │
└─────────────────────────────────────────────┘
```

### Cache Hit Rate Targets

| Cache | Expected Hit Rate | Impact |
|-------|-------------------|--------|
| SQL Cache | 40–60% (repeated questions) | Eliminates LLM cost |
| Schema Cache | 95%+ (schema changes rarely) | Eliminates DB load |
| Connection Pool | 99%+ (persistent server) | Eliminates connect latency |

---

## Security Model

### Defense Layers

```
Layer 1: AST Validation (sqlparse)
  → Block DROP, TRUNCATE, ALTER, GRANT, CREATE
  → Block DELETE/UPDATE without WHERE

Layer 2: EXPLAIN Cost Check
  → Reject queries with estimated cost > threshold
  → Prevents accidental cross-joins on large tables

Layer 3: Auto-LIMIT Injection
  → All SELECTs capped at MAX_RESULT_ROWS (default 100)
  → Prevents result-set exhaustion

Layer 4: Parameterized Introspection
  → Schema queries use $1, %s, ?, :name binds
  → Prevents SQL injection in metadata queries

Layer 5: Connection Pool Isolation
  → Each request gets pooled connection, no shared state
  → Read-only pools recommended for production

Layer 6: Error Sanitization
  → Stack traces logged server-side only
  → Client receives sanitized error messages
```

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Prompt injection → malicious SQL | AST validation blocks dangerous commands |
| Resource exhaustion (large query) | EXPLAIN cost check + auto-LIMIT |
| Data exfiltration (all rows) | Auto-LIMIT 100, paginated results |
| Schema enumeration | Information_schema access required (DB auth) |
| LLM API key exposure | Environment variables only, never logged |

---

## Scaling Considerations

### Horizontal Scaling

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Load       │────→│  dbwhisper  │────→│  dbwhisper  │
│  Balancer   │     │  Instance 1 │     │  Instance 2 │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                     │
                           └──────────┬──────────┘
                                      │
                            ┌─────────┴─────────┐
                            │   Shared Cache    │
                            │   (Redis/S3)      │
                            └───────────────────┘
```

**Shared state needed:**
- SQL Cache → Redis or S3 (optional — local cache is fine for read-only)
- Schema Cache → S3 or shared volume (optional — TTL refresh is cheap)
- Connection pools → Per-instance (no sharing needed)

### Vertical Scaling

| Bottleneck | Solution |
|------------|----------|
| LLM latency | SQL cache, faster model tier, streaming |
| DB throughput | Connection pool sizing, read replicas |
| Schema size | Schema RAG (already implemented) |
| Memory | Streaming results, pagination |

### Recommended Production Setup

```
2+ instances behind load balancer
  → Each instance: 2 CPU, 4GB RAM
  → Connection pools: min=5, max=20 per DB
  → Schema cache: Redis with 1h TTL
  → SQL cache: Redis with infinite TTL
  → LLM: Circuit breaker + fallback provider
  → Monitoring: Structured metrics → Datadog/Prometheus
```

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| MCP Protocol | FastMCP | ≥0.4.0 |
| HTTP Client | httpx | ≥0.27.0 |
| SQL Parsing | sqlparse | ≥0.5.0 |
| PostgreSQL | asyncpg | ≥0.29.0 |
| MySQL | aiomysql | ≥0.2.0 |
| MSSQL | aioodbc | ≥0.5.0 |
| SQLite | aiosqlite | ≥0.20.0 |
| Oracle | oracledb | ≥2.0.0 |
| OpenAI SDK | openai | ≥1.0.0 |
| Anthropic SDK | anthropic | ≥0.28.0 |
| AWS | boto3 | ≥1.34.0 |
| Environment | python-dotenv | ≥1.0.0 |
| Validation | pydantic | ≥2.0.0 |

---

## Directory Structure

```
dbwhisper/
├── app/
│   ├── __init__.py
│   ├── server.py                  # FastMCP setup
│   ├── run_mcp.py                 # Entry point
│   ├── tools.py                   # MCP tool handlers (pipeline entry)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # Pipeline framework
│   │   ├── metrics.py             # Request telemetry
│   │   ├── circuit_breaker.py   # Failure isolation
│   │   └── cache.py               # Disk cache manager
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_factory.py         # Provider routing + fallback
│   │   ├── db_factory.py          # Database routing
│   │   ├── schema_rag.py          # Table selection (RAG)
│   │   ├── domain_context.py      # Domain context loader + RAG
│   │   ├── sql_validator.py       # AST + EXPLAIN validation
│   │   ├── sql_cache.py           # Generated SQL cache
│   │   ├── schema_loader.py       # Legacy wrapper (with cache)
│   │   ├── db_executor.py         # Legacy wrapper (with pool)
│   │   ├── pipeline_stages.py     # All 10 pipeline stages
│   │   ├── llm_providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # BaseLLMClient abstract class
│   │   │   ├── openai_provider.py # OpenAI SDK-based
│   │   │   ├── azure_provider.py  # httpx-based, 4 API patterns
│   │   │   ├── claude_provider.py # Anthropic SDK-based
│   │   │   ├── kimi_provider.py   # OpenAI-compatible
│   │   │   └── bedrock_provider.py # boto3 Converse API
│   │   └── databases/
│   │       ├── __init__.py
│   │       ├── base.py            # BaseDatabase abstract class
│   │       ├── postgres.py        # asyncpg pool
│   │       ├── mysql.py           # aiomysql pool
│   │       ├── mssql.py           # aioodbc pool
│   │       ├── sqlite.py          # aiosqlite
│   │       └── oracle.py          # oracledb pool
│   └── util/
│       ├── __init__.py
│       └── config.py              # Settings + backward compat
├── context/
│   ├── business_rules.md          # Example domain rules
│   └── definitions.md             # Example definitions
├── cache/                         # Runtime cache directory
├── data/                          # SQLite default path
├── .env.example                   # Configuration template
├── requirements.txt               # Dependencies
├── README.md                      # User documentation
└── ARCHITECTURE.md               # This file
```

---

## Configuration Reference

### Performance Tuning

| Variable | Default | When to Change |
|----------|---------|---------------|
| `SCHEMA_CACHE_TTL` | 3600 | Lower for dev (frequent schema changes), higher for prod |
| `RAG_TOP_K` | 5 | Lower for very simple schemas, higher for complex multi-table queries |
| `MAX_RESULT_ROWS` | 100 | Lower for safety, higher for analytics dashboards |
| `EXPLAIN_MAX_COST` | 100000 | Lower for production safety, higher for analytics workloads |
| `CIRCUIT_BREAKER_THRESHOLD` | 5 | Lower for faster failover, higher for transient tolerance |
| `CIRCUIT_BREAKER_TIMEOUT` | 60 | Shorter for aggressive recovery, longer for rate-limited APIs |

### Provider Selection

| Scenario | Recommended Provider |
|----------|---------------------|
| Azure enterprise | `azure` with `LLM_PROVIDER_FALLBACK=openai` |
| Cost-sensitive | `openai` (gpt-4o-mini) or `kimi` |
| Maximum reasoning | `azure` with o3-pro or `claude` |
| AWS-native | `bedrock` |
| China market | `kimi` (Moonshot) |

---

## Glossary

| Term | Definition |
|------|------------|
| **MCP** | Model Context Protocol — standard for AI tool integration |
| **RAG** | Retrieval-Augmented Generation — fetch relevant context instead of sending everything |
| **Schema RAG** | Select only relevant database tables for the LLM prompt |
| **Circuit Breaker** | Pattern that stops calling a failing service and redirects to fallback |
| **AST** | Abstract Syntax Tree — parsed representation of SQL for validation |
| **EXPLAIN** | Database command that estimates query cost without executing |
| **Connection Pool** | Reusable set of database connections to avoid per-request overhead |
| **Auto-LIMIT** | Automatically appending row limits to prevent large result sets |
| **Token** | Unit of LLM input/output (roughly 0.75 words) |
| **Prompt** | The full text sent to an LLM (system instructions + context + query) |

---

## Changelog

| Version | Date | Key Changes |
|---------|------|-------------|
| v1.0 | 2025 | Single provider (Azure), single DB (PostgreSQL), basic tools |
| v2.0 | 2026-06 | Pipeline architecture, Schema RAG, SQL cache, circuit breaker, async pools, httpx Azure, 5 databases, 5 LLM providers, structured metrics |

---

*End of Architecture Document*
