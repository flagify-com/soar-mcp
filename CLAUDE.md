# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **SOAR MCP Server** (v1.2.2) designed specifically for the [OctoMation SOAR Platform](https://github.com/flagify-com/OctoMation). It bridges SOAR (Security Orchestration, Automation and Response) capabilities to AI clients through the Model Context Protocol (MCP).

## Architecture

### Core Components

- **`soar_mcp_server.py`** - Main FastMCP server implementing MCP tools, resources, Flask admin app, periodic sync, and entry point
- **`models.py`** - SQLAlchemy database models (BigInteger IDs) and Pydantic schemas; `DatabaseManager` uses `@contextmanager` sessions
- **`sync_service.py`** - Asynchronous service for syncing data from OctoMation SOAR API via `httpx.AsyncClient`
- **`auth_utils.py`** - Authentication management: **bcrypt** password hashing, JWT with persistent secret key
- **`config_manager.py`** - Thread-safe configuration management with database persistence and cache
- **`auth_provider.py`** - SOAR authentication provider for MCP integration (prepared, not wired in yet)
- **`logger_config.py`** - Centralized logging with `RotatingFileHandler` (10MB/file, 5 backups)

### Dual Server Architecture

The system runs **two servers simultaneously**:

1. **MCP Server** (default port 12345): FastMCP-based server providing MCP tools and resources
2. **Web Admin Server** (default port 12346): Flask-based web management interface

Both default to binding on `127.0.0.1` (configurable via `BIND_HOST`).

### MCP Tools (Available to AI Clients)

- `list_playbooks_quick` - Get concise playbook list (ID, name, displayName) — sync
- `query_playbook_execution_params` - Get playbook parameter definitions — sync
- `execute_playbook` - Execute SOAR playbooks with parameters — **async** (httpx)
- `query_playbook_execution_status_by_activity_id` - Check execution status — **async**
- `query_playbook_execution_result_by_activity_id` - Get detailed results — **async**

### Key Technical Details

- **Playbook IDs**: BigInteger (64-bit), support both integer and string formats
- **Authentication**: Token-based via URL parameters (`?token=xxxx`)
- **Password Hashing**: **bcrypt** (salted), replaces SHA-256
- **JWT Secret**: Persisted in database, survives server restarts
- **Database**: SQLite with SQLAlchemy ORM; sessions via `@contextmanager`
- **Async Architecture**: `httpx.AsyncClient` (shared instance) for SOAR API calls; `contextvars.ContextVar` for request context (replaces `threading.local`)
- **Execution Records**: `BoundedDict` (max 1000 entries, LRU eviction)
- **Periodic Sync**: Background thread with persistent event loop
- **SSL Verification**: Defaults to **enabled**; configurable per-client (not globally overridden)

## Common Commands

### Development Setup
```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your OctoMation SOAR API credentials
```

### Running the Server
```bash
# Start both MCP and Web servers
python3 soar_mcp_server.py

# Or use the startup script
./start_simple_server.sh
```

### Testing

```bash
# Test MCP client connection
cd tests
python mcp_soar_client.py

# Test specific playbook tools
python test_new_playbook_tools.py --playbook-id 1907203516548373

# Test real API integration
python test_real_api.py

# Test playbook execution (use actual test data)
python test_unified_execute_playbook.py --playbook-id 1907203516548373

# Run automation test suite
./test_automation.sh
```

### Password Management
```bash
# Interactive mode (choose random or custom password)
./reset_admin_password.sh

# Generate random password
./reset_admin_password.sh --random

# Set specific password
./reset_admin_password.sh --set 'YourPassword'
```

### Configuration
- **Web Admin**: `http://127.0.0.1:12346/admin` (configure SOAR API settings)
- **MCP Endpoint**: `http://127.0.0.1:12345/mcp?token=xxxx`
- **Environment**: `.env` file for initial configuration; runtime config stored in database

## Test Data Parameters

When testing playbook execution, use these parameters (from actual OctoMation setup):

```json
{
    "eventId": 0,
    "executorInstanceId": 1907203516548373,
    "executorInstanceType": "PLAYBOOK",
    "params": [
        {
            "key": "src",
            "value": "15.197.148.33"
        }
    ]
}
```

## MCP Client Configuration

For Cherry Studio, Claude Desktop, and other MCP clients:

```json
{
  "mcpServers": {
    "soar-mcp": {
      "type": "http",
      "name": "soar-mcp",
      "description": "SOAR 安全编排平台集成",
      "url": "http://127.0.0.1:12345/mcp?token=xxxx"
    }
  }
}
```

Replace `xxxx` with actual API token from web admin interface.

## Important Notes

- SSL verification **enabled by default** (`SSL_VERIFY=1`); set to `0` only for self-signed certificate environments
- Supports both Chinese and English interfaces
- Requires active OctoMation SOAR platform connection
- `contextvars.ContextVar` used for async-safe request context (not `threading.local`)
- All MCP tool calls are recorded in audit logs
- Admin passwords use **bcrypt** hashing; old SHA-256 hashes are incompatible (re-generate on upgrade)
- Log files auto-rotate at 10MB with 5 backups in `logs/` directory
