# Generator

The Generator creates new agents from natural language descriptions using LLMs.

## Overview

```bash
forge-agent generate "monitor stock prices and send alerts"
```

This command:

1. Parses the description
2. Extracts requirements (domain, capabilities, agent type)
3. Generates Python code using an LLM
4. Validates the code (syntax, types, security)
5. Sandboxes the code (isolated execution test)
6. Saves to `generated_agents/` with MANIFEST.json

## How It Works

### 1. Requirements Parsing

```python
from forge_agent.generator.parser import RequirementsParser

parser = RequirementsParser()
reqs = parser.parse("monitor stock prices and send alert")

print(reqs.domain)          # "finance"
print(reqs.capabilities)    # ["web_scraping", "alerting"]
print(reqs.agent_type)      # AgentType.SCRAPER
```

### 2. Code Generation

```python
from forge_agent.generator.generator import CodeGenerator

generator = CodeGenerator()
code = await generator.generate(reqs)

print(code)  # Complete Python module
```

### 3. Validation

```python
from forge_agent.generator.validator import CodeValidator

validator = CodeValidator()
result = validator.validate(code)

print(result.passed)        # True/False
print(result.errors)        # List of validation errors
```

### 4. Sandboxing

```python
from forge_agent.generator.sandbox import SandboxRunner

sandbox = SandboxRunner()
result = await sandbox.run(code)

print(result.success)       # True/False
print(result.stdout)        # Output
print(result.stderr)        # Errors
```

## Agent Types

The generator supports specialized agent types:

- **SCRAPER** — Web scraping agents
- **ANALYZER** — Data analysis agents
- **MONITOR** — Monitoring agents
- **GENERATOR** — Content generation agents
- **CUSTOM** — User-defined types

Each type gets tailored prompts and templates.

## Configuration

### LLM Provider

```bash
# Set primary provider
export FORGE_LLM_PRIMARY=openai

# Configure API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### Generation Options

```bash
# Specify agent type
forge-agent generate "..." --type=scraper

# Add MCP tools
forge-agent generate "..." --mcp-tools=filesystem,fetch

# Include datasets
forge-agent generate "..." --dataset=stock_prices.csv
```

## MANIFEST.json

Every generated agent gets a manifest:

```json
{
  "agent_id": "stock.monitor",
  "version": 1,
  "domain": "finance",
  "agent_type": "monitor",
  "description": "Monitor stock prices",
  "capabilities": ["web_scraping", "alerting"],
  "dependencies": ["httpx", "pandas"],
  "validation_status": "passed",
  "sandbox_status": "passed",
  "generated_at": "2026-06-27T10:00:00Z",
  "llm_provider": "openai",
  "llm_model": "gpt-4"
}
```

## Version Management

```bash
# List versions
forge-agent list stock.monitor

# Activate version
forge-agent activate stock.monitor --version 2

# Rollback
forge-agent rollback stock.monitor --version 1

# Delete version
forge-agent delete stock.monitor --version 0
```

## Self-Iteration

Generated agents can improve themselves:

```python
from forge_agent.learning import Optimizer

optimizer = Optimizer()
improved_code = await optimizer.evolve(
    code=original_code,
    feedback=user_feedback,
    metrics=performance_metrics,
)
```

## Example: Generate and Use

```bash
# Generate
forge-agent generate "scrape football scores and notify fans"

# List
forge-agent list

# Run in pipeline
python my_pipeline.py
```

```python
# my_pipeline.py
from forge_agent import Pipeline, PipelineNode, NodeType, PipelineEngine, AgentContext
from generated_agents.football_scraper import FootballScraperAgent

# Register the generated agent
FootballScraperAgent.register()

# Use in pipeline
pipeline = Pipeline(pipeline_id="football.v1")
pipeline.add_node(PipelineNode(
    node_id="scraper",
    node_type=NodeType.AGENT,
    agent_id="football.scraper",
    next_nodes=["done"],
))
pipeline.add_node(PipelineNode(
    node_id="done",
    node_type=NodeType.AGGREGATOR,
))

async def main():
    ctx = AgentContext(scope_id="match-1", scope_name="Premier League")
    state = await PipelineEngine().run(pipeline, ctx)
    print(state["board"].to_dict())
```
