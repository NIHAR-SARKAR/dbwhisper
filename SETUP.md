# dbwhisper — Setup Guide

> Step-by-step instructions to install, configure, and run dbwhisper in any environment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [LLM Provider Setup](#llm-provider-setup)
6. [Domain Context](#domain-context)
7. [Running the Server](#running-the-server)
8. [Testing Your Setup](#testing-your-setup)
9. [Troubleshooting](#troubleshooting)
10. [Production Deployment](#production-deployment)
11. [VS Code Setup](#vs-code-setup)

---

## Prerequisites

### Required

- **Python 3.10+**
- **pip** or **uv**
- **Git**

### Database Drivers (install as needed)

| Database   | System Dependency                                                                                                       |
| ---------- | ----------------------------------------------------------------------------------------------------------------------- |
| PostgreSQL | None (pure Python)                                                                                                      |
| MySQL      | None (pure Python)                                                                                                      |
| MSSQL      | [ODBC Driver 17+ for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) |
| SQLite     | None (built-in)                                                                                                         |
| Oracle     | None (pure Python)                                                                                                      |

### LLM Provider Requirements

| Provider | Requirement                                                         |
| -------- | ------------------------------------------------------------------- |
| OpenAI   | API key from [platform.openai.com](https://platform.openai.com)     |
| Azure    | Azure OpenAI or Azure AI Foundry deployment                         |
| Claude   | API key from [console.anthropic.com](https://console.anthropic.com) |
| Kimi     | API key from [platform.moonshot.cn](https://platform.moonshot.cn)   |
| Bedrock  | AWS account with Bedrock access                                     |

---

## Installation

### Option 1: Standard (pip)

```bash
# Clone the repository
git clone https://github.com/NIHAR-SARKAR/dbwhisper.git
cd dbwhisper

# Create virtual environment
python -m venv .venv

# Activate (Linux/Mac)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Fast (uv)

```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/NIHAR-SARKAR/dbwhisper.git
cd dbwhisper
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Option 3: Docker (Coming Soon)

```bash
docker build -t dbwhisper .
docker run -p 3004:3004 --env-file .env dbwhisper
```

---

## Configuration

### 1. Create Environment File

```bash
cp .env.example .env
```

### 2. Edit `.env`

Open `.env` in your editor and fill in your credentials.

#### Minimal Configuration (OpenAI + PostgreSQL)

```bash
# LLM Provider
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o

# Database
DB_TYPE=postgresql
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
```

#### Minimal Configuration (Azure + SQLite)

```bash
# LLM Provider
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_ID=gpt-4o

# Database
DB_TYPE=sqlite
SQLITE_DB_PATH=./data/myapp.db
```

#### Full Configuration with Fallback

```bash
# Primary LLM
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_ID=gpt-4o

# Fallback LLM (used when Azure fails 5 times)
LLM_PROVIDER_FALLBACK=openai
OPENAI_API_KEY=sk-your-openai-key
OPENAI_MODEL=gpt-4o-mini

# Database
DB_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
DB_SCHEMA=public

# Performance
SCHEMA_CACHE_TTL=3600
SQL_CACHE_ENABLED=true
RAG_TOP_K=5
MAX_RESULT_ROWS=100

# Domain Context
DOMAIN_CONTEXT_DIR=./context

# Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=3004
```

### 3. Configuration Priority

Environment variables are loaded in this order (later overrides earlier):

1. `.env` file (via `python-dotenv`)
2. System environment variables
3. Code defaults

**Tip:** For production, set secrets via your deployment platform (Kubernetes secrets, AWS Secrets Manager, etc.) rather than `.env`.

---

## Database Setup

### PostgreSQL

```bash
# Install (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb mydb
sudo -u postgres createuser -P myuser  # Set password

# Grant permissions
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;"

# .env
DATABASE_URL=postgresql://myuser:mypass@localhost:5432/mydb
```

### MySQL

```bash
# Install (Ubuntu/Debian)
sudo apt-get install mysql-server

# Create database
sudo mysql -e "CREATE DATABASE mydb;"
sudo mysql -e "CREATE USER 'myuser'@'localhost' IDENTIFIED BY 'mypass';"
sudo mysql -e "GRANT ALL PRIVILEGES ON mydb.* TO 'myuser'@'localhost';"

# .env
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mydb
DB_USER=myuser
DB_PASSWORD=mypass
DB_SCHEMA=mydb
```

### Microsoft SQL Server

```bash
# Install ODBC Driver (Ubuntu 22.04)
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# .env
DB_TYPE=mssql
DB_HOST=localhost
DB_PORT=1433
DB_NAME=mydb
DB_USER=sa
DB_PASSWORD=YourStrong@Passw0rd
DB_SCHEMA=dbo
```

### SQLite

```bash
# No setup needed — SQLite is file-based
mkdir -p data

# .env
DB_TYPE=sqlite
SQLITE_DB_PATH=./data/myapp.db
```

**Note:** The database file will be created automatically on first connection.

### Oracle

```bash
# Install Oracle XE or use existing instance
# Download from oracle.com (requires account)

# .env
DB_TYPE=oracle
DB_HOST=localhost
DB_PORT=1521
DB_NAME=XEPDB1
DB_USER=system
DB_PASSWORD=oracle
DB_SCHEMA=SYSTEM
```

---

## LLM Provider Setup

### OpenAI

1. Go to [platform.openai.com](https://platform.openai.com)
2. Create an API key
3. Add to `.env`:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
# Optional: OPENAI_BASE_URL=https://api.openai.com/v1
```

**Models:** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4`

### Azure OpenAI

1. Create an Azure OpenAI resource in [Azure Portal](https://portal.azure.com)
2. Deploy a model (any name you choose)
3. Get endpoint and key from the resource page
4. Add to `.env`:

```bash
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT_ID=my-gpt4o-deployment
```

**Important:** `AZURE_OPENAI_DEPLOYMENT_ID` can be **any deployment name** — `gpt-4o`, `Meta-Llama-3-70B`, `DeepSeek-R1`, `my-custom-model`. The code passes it directly to the API without validation.

### Azure AI Foundry (Non-OpenAI Models)

1. Go to [ai.azure.com](https://ai.azure.com)
2. Deploy a model from the model catalog (Llama, Mistral, Cohere, etc.)
3. Use the **project endpoint** (not the OpenAI endpoint)
4. Add to `.env`:

```bash
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://my-project.services.ai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT_ID=Meta-Llama-3-70B
```

### Claude (Anthropic)

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an API key
3. Add to `.env`:

```bash
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

**Models:** `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, `claude-3-haiku-20240307`

### Kimi (Moonshot AI)

1. Go to [platform.moonshot.cn](https://platform.moonshot.cn)
2. Create an API key
3. Add to `.env`:

```bash
LLM_PROVIDER=kimi
KIMI_API_KEY=sk-your-key
KIMI_MODEL=moonshot-v1-8k
# Optional: KIMI_BASE_URL=https://api.moonshot.cn/v1
```

**Models:** `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k`

### AWS Bedrock

1. Enable Bedrock in [AWS Console](https://console.aws.amazon.com/bedrock)
2. Create an IAM user with Bedrock runtime permissions
3. Get access key and secret
4. Add to `.env`:

```bash
LLM_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

**Models:** Any model ID from [AWS Bedrock docs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)

---

## Domain Context

Domain context lets you inject business rules and definitions into the LLM prompt without hardcoding them in the database schema.

### 1. Create Context Directory

```bash
mkdir -p context
```

### 2. Add Markdown Files

```bash
cat > context/business_rules.md << 'EOF'
# Business Rules

## Active Records
- A user is considered active if `users.status = 'active'` AND `users.end_date IS NULL`.
- Always filter for active users unless the user explicitly asks for inactive or all users.

## Currency
- All monetary amounts in the `orders` table are stored in USD.
- Use `orders.currency_code` only if joining with `exchange_rates`.
EOF

cat > context/definitions.md << 'EOF'
# Domain Definitions

## Revenue
Revenue = SUM(order_total) where order_status = 'completed' and payment_status = 'paid'.

## Churned User
A user is churned if they have not placed an order in the last 90 days.
EOF
```

### 3. How It Works

- Files are scanned at query time
- Only paragraphs relevant to the query are injected (RAG-based)
- Rules guide the LLM's SQL generation without polluting the schema

**Example:**

```
User: "What was revenue last month?"
→ LLM sees: "Revenue = SUM(order_total) where order_status = 'completed'..."
→ Generates: SELECT SUM(order_total) FROM orders WHERE order_status = 'completed' AND ...
```

---

## Running the Server

### Development Mode

```bash
# Standard
python app/run_mcp.py

# With verbose logging
LOG_LEVEL=debug python app/run_mcp.py

# Custom port
MCP_SERVER_PORT=3004 python app/run_mcp.py
```

### Production Mode

```bash
# Using Gunicorn (for HTTP transport)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.run_mcp:app

# Using PM2
pm2 start app/run_mcp.py --name dbwhisper --interpreter python

# Using systemd (create /etc/systemd/system/dbwhisper.service)
[Unit]
Description=dbwhisper MCP Server
After=network.target

[Service]
Type=simple
User=dbwhisper
WorkingDirectory=/opt/dbwhisper
ExecStart=/opt/dbwhisper/.venv/bin/python app/run_mcp.py
Restart=always
Environment=PYTHONPATH=/opt/dbwhisper

[Install]
WantedBy=multi-user.target
```

### Background Mode

```bash
# Linux/Mac
nohup python app/run_mcp.py > dbwhisper.log 2>&1 &

# Or use screen/tmux
screen -S dbwhisper
python app/run_mcp.py
# Ctrl+A, D to detach
```

---

## Testing Your Setup

### 1. Health Check

```bash
curl http://localhost:3004/health
# Expected: {"status": "ok", "version": "2.0.0"}
```

### 2. Get Database Metadata

```bash
curl -X POST http://localhost:3004/tools/get_db_metadata   -H "Content-Type: application/json"   -d '{}'
```

**Expected:** JSON with schema tables, domain context, and dialect.

### 3. Natural Language Query

```bash
curl -X POST http://localhost:3004/tools/handle_user_query   -H "Content-Type: application/json"   -d '{"task_input": "Show me top 5 users by total order amount"}'
```

**Expected:** JSON with `sql`, `results`, and `meta` fields.

### 4. Using MCP Inspector

```bash
# Install inspector
npm install -g @modelcontextprotocol/inspector

# Run
mcp-inspector
# Enter server URL: http://localhost:3004
```

### 5. Using Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dbwhisper": {
      "command": "python",
      "args": ["/path/to/dbwhisper/app/run_mcp.py"],
      "env": {
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-...",
        "DB_TYPE": "postgresql",
        "DATABASE_URL": "postgresql://..."
      }
    }
  }
}
```

Then ask Claude: _"Use dbwhisper to show me the top 5 customers by revenue"_

---

## Troubleshooting

### "Module not found" errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Check Python version
python --version  # Must be 3.10+
```

### Database connection refused

```bash
# PostgreSQL
sudo systemctl status postgresql
sudo systemctl start postgresql

# MySQL
sudo systemctl status mysql
sudo systemctl start mysql

# Test connection manually
psql $DATABASE_URL -c "SELECT 1"
```

### "ODBC Driver 17 not found" (MSSQL)

```bash
# Ubuntu/Debian
sudo apt-get install unixodbc unixodbc-dev msodbcsql17

# macOS
brew install unixodbc msodbcsql17

# Verify
odbcinst -q -d -n "ODBC Driver 17 for SQL Server"
```

### Azure "Deployment not found"

- Double-check `AZURE_OPENAI_DEPLOYMENT_ID` matches exactly (case-sensitive)
- Verify the deployment is active in Azure OpenAI Studio
- Check `AZURE_OPENAI_ENDPOINT` has no trailing `/openai/` — the code adds it

### Claude "max_tokens required"

The Claude provider sets `max_tokens=4000` by default. If you need more:

```bash
# Edit app/services/llm_providers/claude_provider.py
# Change max_tokens=4000 to max_tokens=8000
```

### Slow responses

| Symptom          | Cause                | Fix                                             |
| ---------------- | -------------------- | ----------------------------------------------- |
| Every query slow | Schema cache miss    | Check `cache/` directory exists and is writable |
| First query slow | Connection pool cold | Normal — pools warm up after first request      |
| LLM call slow    | Network latency      | Use `LLM_PROVIDER_FALLBACK` with faster model   |
| High token usage | Schema RAG disabled  | Verify `RAG_TOP_K` is set (default 5)           |

### Circuit breaker tripped

```bash
# Check logs
grep "Circuit breaker" dbwhisper.log

# Reset by restarting server
# Or wait CIRCUIT_BREAKER_TIMEOUT seconds (default 60)
```

---

## Production Deployment

### Environment Checklist

- [ ] `.env` file NOT committed to git (use `.env.example` as template)
- [ ] Secrets managed via Kubernetes secrets, AWS Secrets Manager, or HashiCorp Vault
- [ ] Database user has **read-only** permissions (no DROP, CREATE, INSERT)
- [ ] `MAX_RESULT_ROWS` set to appropriate limit (100 for safety, 1000 for analytics)
- [ ] `EXPLAIN_MAX_COST` tuned for your database size
- [ ] `CIRCUIT_BREAKER_THRESHOLD` and `LLM_PROVIDER_FALLBACK` configured
- [ ] `SCHEMA_CACHE_TTL` set based on schema change frequency
- [ ] Logging configured to centralized system (Datadog, Splunk, ELK)
- [ ] Health check endpoint monitored (load balancer / Kubernetes probe)

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 3004

CMD ["python", "app/run_mcp.py"]
```

```bash
docker build -t dbwhisper:latest .
docker run -d -p 3004:3004 --env-file .env --name dbwhisper dbwhisper:latest
```

### Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dbwhisper
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dbwhisper
  template:
    metadata:
      labels:
        app: dbwhisper
    spec:
      containers:
        - name: dbwhisper
          image: dbwhisper:latest
          ports:
            - containerPort: 3004
          envFrom:
            - secretRef:
                name: dbwhisper-secrets
            - configMapRef:
                name: dbwhisper-config
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 3004
            initialDelaySeconds: 10
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: dbwhisper
spec:
  selector:
    app: dbwhisper
  ports:
    - port: 80
      targetPort: 3004
  type: ClusterIP
```

---

## VS Code Setup

### Recommended Extensions

Create `.vscode/extensions.json`:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "ms-python.debugpy",
    "eamodio.gitlens",
    "redhat.vscode-yaml"
  ]
}
```

### Launch Configurations

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run dbwhisper Server",
      "type": "python",
      "request": "launch",
      "module": "app.run_mcp",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "justMyCode": false,
      "envFile": "${workspaceFolder}/.env"
    },
    {
      "name": "Debug Tools",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/app/tools.py",
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

### Tasks

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Install Requirements",
      "type": "shell",
      "command": "${workspaceFolder}/.venv/bin/pip",
      "args": ["install", "-r", "requirements.txt"],
      "group": "build"
    },
    {
      "label": "Run Server",
      "type": "shell",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "app.run_mcp"],
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "options": {
        "env": {
          "PYTHONPATH": "${workspaceFolder}"
        }
      }
    },
    {
      "label": "Format Code",
      "type": "shell",
      "command": "${workspaceFolder}/.venv/bin/black",
      "args": ["app/"],
      "group": "build"
    }
  ]
}
```

---

## Next Steps

1. **Read the architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Explore the code:** Start with `app/tools.py` and `app/services/pipeline_stages.py`
3. **Customize:** Add your own domain context files in `context/`
4. **Monitor:** Watch structured metrics in your logs
5. **Optimize:** Tune `RAG_TOP_K`, `MAX_RESULT_ROWS`, and `EXPLAIN_MAX_COST` for your workload

---

## Getting Help

- 📖 **Documentation:** [README.md](README.md) · [ARCHITECTURE.md](ARCHITECTURE.md)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/NIHAR-SARKAR/dbwhisper/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/NIHAR-SARKAR/dbwhisper/discussions)

---

> **Happy querying!** 🎯
