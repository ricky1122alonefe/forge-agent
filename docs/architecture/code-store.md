# CodeStore

The CodeStore manages versioned storage of generated agents.

## Overview

Every generated agent is stored with:

- **Code** — Python source file
- **Manifest** — Metadata (MANIFEST.json)
- **Version** — Incremental version number

## Directory Structure

```
generated_agents/
├── stock.monitor/
│   ├── v0/
│   │   ├── agent.py
│   │   └── MANIFEST.json
│   ├── v1/
│   │   ├── agent.py
│   │   └── MANIFEST.json
│   └── v2/
│       ├── agent.py
│       └── MANIFEST.json
└── stock.analyzer/
    └── v0/
        ├── agent.py
        └── MANIFEST.json
```

## Using CodeStore

### List Agents

```python
from forge_agent.generator.store import CodeStore

store = CodeStore(root="generated_agents")

# List all agents
agents = store.list_agents()
print(agents)  # ["stock.monitor", "stock.analyzer"]

# List versions
versions = store.list_versions("stock.monitor")
print(versions)  # [0, 1, 2]
```

### Get Code

```python
# Get latest version
code = store.get_code("stock.monitor")

# Get specific version
code = store.get_code("stock.monitor", version=1)
```

### Get Manifest

```python
manifest = store.get_manifest("stock.monitor", version=2)

print(manifest["agent_id"])
print(manifest["domain"])
print(manifest["validation_status"])
```

### Activate Version

```python
# Activate version 1
store.activate("stock.monitor", version=1)

# Get active version
active = store.get_active_version("stock.monitor")
print(active)  # 1
```

### Rollback

```python
# Rollback to previous version
store.rollback("stock.monitor")

# Rollback to specific version
store.rollback("stock.monitor", version=0)
```

### Delete Version

```python
# Delete version 0
store.delete_version("stock.monitor", version=0)
```

## MANIFEST.json

Every version includes a manifest:

```json
{
  "agent_id": "stock.monitor",
  "version": 2,
  "domain": "finance",
  "agent_type": "monitor",
  "description": "Monitor stock prices and send alerts",
  "capabilities": ["web_scraping", "alerting"],
  "dependencies": ["httpx", "pandas"],
  "validation_status": "passed",
  "sandbox_status": "passed",
  "generated_at": "2026-06-27T10:00:00Z",
  "llm_provider": "openai",
  "llm_model": "gpt-4",
  "tokens_used": 1500,
  "generation_time_ms": 3200
}
```

## Version Management

### Automatic Versioning

Each generation creates a new version:

```python
from forge_agent.generator.generator import CodeGenerator

generator = CodeGenerator()
code = await generator.generate(requirements)

# Automatically saved as next version
store.save("stock.monitor", code, manifest)
```

### Manual Versioning

```python
# Save with custom metadata
store.save(
    agent_id="stock.monitor",
    code=code,
    manifest={
        "custom_field": "value",
        "notes": "Added error handling",
    },
)
```

## CLI Commands

```bash
# List agents
forge-agent list

# List versions
forge-agent list stock.monitor

# Activate version
forge-agent activate stock.monitor --version 2

# Rollback
forge-agent rollback stock.monitor --version 1

# Delete version
forge-agent delete stock.monitor --version 0
```

## Storage Backends

### Local Filesystem (Default)

```python
store = CodeStore(root="generated_agents")
```

### SQLite (Planned)

```python
store = SqliteCodeStore(db_path="agents.db")
```

### Cloud Storage (Planned)

```python
store = S3CodeStore(bucket="my-agents", prefix="generated/")
```

## Best Practices

1. **Never delete active version** — Always activate another version first
2. **Keep history** — Don't delete old versions, you might need them
3. **Document changes** — Add notes to manifest
4. **Test before activate** — Validate in staging environment
5. **Monitor storage** — Clean up old versions periodically

## Example: Version Workflow

```python
from forge_agent.generator.store import CodeStore

store = CodeStore(root="generated_agents")

# Generate new version
# ... (generation code)
store.save("stock.monitor", new_code, new_manifest)

# Test in staging
staging_agent = store.load("stock.monitor", version=3)
# ... (run tests)

# Activate if tests pass
store.activate("stock.monitor", version=3)

# Monitor in production
# ... (watch metrics)

# Rollback if issues
store.rollback("stock.monitor", version=2)
```
