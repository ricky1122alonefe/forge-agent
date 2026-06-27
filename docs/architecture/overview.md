# Architecture Overview

forge-agent follows a layered architecture designed for extensibility and separation of concerns.

## Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Generator Layer   LLM-driven Agent code generation + validate│
├─────────────────────────────────────────────────────────────┤
│  Pipeline Layer    DAG / parallel / conditional / aggregator  │
├─────────────────────────────────────────────────────────────┤
│  Registry + Scheduler    agent lifecycle & task execution    │
├─────────────────────────────────────────────────────────────┤
│  Core Layer        BaseAgent + 5 mandatory capabilities       │
│                    (log / search / learn / iterate / prompt) │
└─────────────────────────────────────────────────────────────┘
```

## Core Layer

The foundation that never changes:

- **BaseAgent** — Abstract base class with lifecycle contract
- **AgentContext** — Execution context passed to all methods
- **AgentReport** — Structured output from agents
- **Capabilities** — Pluggable functionality (log, search, learn, iterate, prompt)

## Registry + Scheduler Layer

Manages agent lifecycle:

- **Registry** — Agent registration and discovery
- **Scheduler** — Task scheduling and execution
- **Version Management** — Code versioning and rollback

## Pipeline Layer

Orchestrates multiple agents:

- **Pipeline** — DAG definition
- **PipelineNode** — Individual execution units
- **PipelineEngine** — Execution engine with parallel support
- **Aggregator** — Result combination logic

## Generator Layer

Creates new agents from natural language:

- **RequirementsParser** — Extracts domain, capabilities, type
- **CodeGenerator** — LLM-driven code generation
- **CodeValidator** — Syntax, type, and security validation
- **SandboxRunner** — Isolated execution testing
- **CodeStore** — Versioned storage

## Design Principles

### 1. Contract-Driven

Every agent must implement the same lifecycle:

```python
observe → decide → act → reflect → learn
```

### 2. Business-Agnostic Base

The core framework knows nothing about specific domains. All domain logic lives in generated agents.

### 3. Code-Level Extension

Unlike config-based frameworks, forge-agent generates actual Python code that can be inspected, tested, and modified.

### 4. Sandboxed by Default

Generated code runs in isolated subprocesses with resource limits.

### 5. Observable

Built-in structured logging, tracing, and metrics.

## Data Flow

### Agent Execution

```
AgentContext
    ↓
observe() → observation dict
    ↓
decide() → decision dict
    ↓
act() → AgentReport
    ↓
reflect() → reflection dict
    ↓
learn() → updated state
```

### Pipeline Execution

```
Pipeline + AgentContext
    ↓
PipelineEngine.run()
    ↓
┌─────────────────┐
│ Node 1 (AGENT)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Node 2 (AGENT)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Node 3 (AGG)    │
└────────┬────────┘
         ↓
AgentBoard (final state)
```

### Code Generation

```
Natural Language Description
    ↓
RequirementsParser.parse()
    ↓
AgentRequirements
    ↓
CodeGenerator.generate()
    ↓
Python Code
    ↓
CodeValidator.validate()
    ↓
SandboxRunner.run()
    ↓
CodeStore.save()
    ↓
Generated Agent
```

## Extension Points

### Custom Capabilities

```python
class MyCapability(Capability):
    async def execute(self, ctx: dict) -> dict:
        # Your logic
        return {"result": "done"}
```

### Custom Node Types

```python
pipeline.add_node(PipelineNode(
    node_id="custom",
    node_type=NodeType.FUNCTION,
    func=my_custom_function,
))
```

### Custom LLM Providers

```python
class MyProvider(LLMProvider):
    async def chat(self, messages: list[dict]) -> LLMResponse:
        # Your implementation
        return LLMResponse(content="...", tokens_in=0, tokens_out=0)
```

## Module Structure

```
forge_agent/
├── core/              # BaseAgent, context, report, capabilities
├── registry/          # Agent registration and discovery
├── scheduler/         # Task scheduling
├── pipeline/          # DAG orchestration
├── generator/         # Code generation
│   ├── parser.py      # Requirements parsing
│   ├── generator.py   # Code generation
│   ├── validator.py   # Code validation
│   ├── sandbox.py     # Sandboxed execution
│   └── store.py       # Versioned storage
├── llm/               # LLM providers
├── mcp/               # Model Context Protocol
├── observability/     # Logging, tracing, metrics
├── learning/          # Self-iteration
├── cli/               # Command-line interface
└── exceptions.py      # Error hierarchy
```

## Security Model

### Sandboxing

- Generated code runs in subprocess
- Resource limits (CPU, memory, time)
- Network access controlled
- File system access restricted

### Validation

- Syntax checking (ast.parse)
- Type checking (mypy)
- Security scanning (bandit)
- Import restrictions

### Isolation

- Each agent has its own context
- No shared state between agents
- Explicit data passing via AgentBoard

## Performance Considerations

### Async by Default

All lifecycle methods are async for I/O efficiency.

### Connection Pooling

LLM and MCP clients reuse connections.

### Caching

Prompt templates and generated code are cached.

### Parallel Execution

Pipeline nodes without dependencies run concurrently.

## Future Directions

- **Distributed tracing** — OpenTelemetry integration (✅ T3.5)
- **Dashboard** — Web UI for monitoring
- **Multi-tenancy** — Isolated agent environments
- **Auto-scaling** — Dynamic resource allocation
