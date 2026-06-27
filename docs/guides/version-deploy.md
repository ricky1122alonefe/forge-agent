# Version & Deploy

Manage agent versions and deploy to production.

## Version Management

### List Versions

```bash
forge-agent list stock.monitor
```

Output:

```
stock.monitor
  Version 2 (active) - 2026-06-27 10:00:00
  Version 1          - 2026-06-26 15:00:00
  Version 0          - 2026-06-25 12:00:00
```

### Activate a Version

```bash
forge-agent activate stock.monitor --version 2
```

### Rollback

```bash
forge-agent rollback stock.monitor --version 1
```

### Delete a Version

```bash
forge-agent delete stock.monitor --version 0
```

## CodeStore

Every generated agent is stored in the CodeStore:

```python
from forge_agent.generator.store import CodeStore

store = CodeStore(root="generated_agents")

# List all agents
agents = store.list_agents()

# Get specific version
code = store.get_code("stock.monitor", version=2)

# Get manifest
manifest = store.get_manifest("stock.monitor", version=2)
```

## Deployment Strategies

### 1. Direct Import

```python
from generated_agents.stock_monitor import StockMonitorAgent

# Register the agent
StockMonitorAgent.register()

# Use in pipeline
pipeline.add_node(PipelineNode(
    node_id="monitor",
    node_type=NodeType.AGENT,
    agent_id="stock.monitor",
))
```

### 2. Dynamic Loading

```python
from forge_agent.generator.loader import load_agent

# Load from CodeStore
AgentClass = load_agent("stock.monitor", version=2)

# Register and use
AgentClass.register()
```

### 3. Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY generated_agents/ ./generated_agents/
COPY main.py .

CMD ["python", "main.py"]
```

```python
# main.py
from forge_agent import Pipeline, PipelineNode, NodeType, PipelineEngine, AgentContext
from forge_agent.generator.loader import load_agent
import asyncio

async def main():
    # Load agents
    MonitorAgent = load_agent("stock.monitor")
    AnalyzerAgent = load_agent("stock.analyzer")

    MonitorAgent.register()
    AnalyzerAgent.register()

    # Build pipeline
    pipeline = Pipeline(pipeline_id="stock.v1")
    pipeline.add_node(PipelineNode(
        node_id="monitor",
        node_type=NodeType.AGENT,
        agent_id="stock.monitor",
        next_nodes=["analyzer"],
    ))
    pipeline.add_node(PipelineNode(
        node_id="analyzer",
        node_type=NodeType.AGENT,
        agent_id="stock.analyzer",
        next_nodes=["done"],
    ))
    pipeline.add_node(PipelineNode(
        node_id="done",
        node_type=NodeType.AGGREGATOR,
    ))

    # Run
    ctx = AgentContext(scope_id="prod-1", scope_name="production")
    state = await PipelineEngine().run(pipeline, ctx)
    print(state["board"].to_dict())

asyncio.run(main())
```

## Production Checklist

### Code Quality

- [ ] All tests passing
- [ ] Type hints complete
- [ ] Docstrings present
- [ ] Error handling robust
- [ ] Logging comprehensive

### Configuration

- [ ] Environment variables set
- [ ] API keys configured
- [ ] LLM provider selected
- [ ] MCP servers accessible

### Monitoring

- [ ] Structured logging enabled
- [ ] Tracing configured
- [ ] Metrics collection active
- [ ] Alerting rules defined

### Security

- [ ] Sandbox enabled
- [ ] Input validation active
- [ ] Secrets in environment variables
- [ ] Network access restricted

### Performance

- [ ] Connection pooling enabled
- [ ] Caching configured
- [ ] Rate limiting active
- [ ] Resource limits set

## CI/CD Integration

### GitHub Actions

```yaml
name: Deploy Agents

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install forge-agent[all]

      - name: Run tests
        run: |
          pytest tests/

      - name: Validate agents
        run: |
          forge-agent doctor
          forge-agent list

      - name: Deploy
        run: |
          # Your deployment script
          ./deploy.sh
```

## Best Practices

1. **Version everything** — Never overwrite, always create new versions
2. **Test before deploy** — Run full test suite
3. **Use staging** — Test in staging environment first
4. **Monitor after deploy** — Watch for errors and performance issues
5. **Document changes** — Keep changelog updated
6. **Automate rollback** — Quick rollback on failure
