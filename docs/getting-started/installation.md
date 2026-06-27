# Installation

## Requirements

- Python 3.10+
- pip 23.0+

## Basic Installation

```bash
pip install forge-agent
```

## Optional Dependencies

forge-agent provides several optional dependency groups:

### LLM Providers

```bash
pip install "forge-agent[llm]"
```

Installs: `openai>=1.30`, `anthropic>=0.25`

### MCP (Model Context Protocol)

```bash
pip install "forge-agent[mcp]"
```

Installs: `mcp>=1.0`

### Search

```bash
pip install "forge-agent[search]"
```

Installs: `httpx>=0.27`, `tavily-python>=0.3`

### OpenTelemetry

```bash
pip install "forge-agent[otel]"
```

Installs: `opentelemetry-api>=1.20`, `opentelemetry-sdk>=1.20`

### All Extras

```bash
pip install "forge-agent[all]"
```

## Development Installation

```bash
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent
pip install -e ".[dev]"
pre-commit install
```

## Verify Installation

```bash
forge-agent --version
forge-agent doctor
```

The `doctor` command checks your environment:

- Python version
- Package installation
- Optional dependencies
- LLM configuration
- Generated agents directory
- SQLite availability
