# Pipeline

Pipelines orchestrate multiple agents in a directed acyclic graph (DAG).

## Overview

A pipeline consists of nodes connected by edges. Each node can be:

- **AGENT** — Executes a registered agent
- **FUNCTION** — Runs a custom function
- **AGGREGATOR** — Combines results from multiple nodes

## Creating a Pipeline

```python
from forge_agent import Pipeline, PipelineNode, NodeType

pipeline = Pipeline(pipeline_id="analysis.v1")

# Add nodes
pipeline.add_node(PipelineNode(
    node_id="scraper",
    node_type=NodeType.AGENT,
    agent_id="web.scraper",
    next_nodes=["analyzer"],
))

pipeline.add_node(PipelineNode(
    node_id="analyzer",
    node_type=NodeType.AGENT,
    agent_id="data.analyzer",
    next_nodes=["aggregator"],
))

pipeline.add_node(PipelineNode(
    node_id="aggregator",
    node_type=NodeType.AGGREGATOR,
))
```

## Running a Pipeline

```python
from forge_agent import PipelineEngine, AgentContext

engine = PipelineEngine()
ctx = AgentContext(scope_id="run-1", scope_name="analysis")

state = await engine.run(pipeline, ctx)

board = state["board"]
print(f"Verdict: {board.verdict}")
print(f"Reports: {len(board.reports)}")
```

## Node Types

### AGENT

Executes a registered agent by `agent_id`.

```python
PipelineNode(
    node_id="my-agent",
    node_type=NodeType.AGENT,
    agent_id="domain.agent_id",
    next_nodes=["next-node"],
)
```

### FUNCTION

Runs a custom async function.

```python
async def my_function(ctx: AgentContext, board: AgentBoard) -> dict:
    return {"result": "processed"}

PipelineNode(
    node_id="custom-func",
    node_type=NodeType.FUNCTION,
    func=my_function,
    next_nodes=["next-node"],
)
```

### AGGREGATOR

Combines results from all incoming nodes.

```python
PipelineNode(
    node_id="final",
    node_type=NodeType.AGGREGATOR,
)
```

## Parallel Execution

Nodes without dependencies run in parallel:

```python
pipeline.add_node(PipelineNode(
    node_id="scraper1",
    node_type=NodeType.AGENT,
    agent_id="web.scraper1",
    next_nodes=["aggregator"],
))

pipeline.add_node(PipelineNode(
    node_id="scraper2",
    node_type=NodeType.AGENT,
    agent_id="web.scraper2",
    next_nodes=["aggregator"],
))

# Both scrapers run in parallel
```

## Conditional Edges

Add conditions to edges:

```python
pipeline.add_edge(
    from_node="analyzer",
    to_node="alerter",
    condition=lambda board: board.confidence < 0.5,
)
```

## Tracing

Pipelines automatically create traces:

```python
from forge_agent.observability import get_trace_manager

mgr = get_trace_manager()
trace = mgr.current_trace

print(trace.summary())
```

## Example: Stock Analysis Pipeline

```python
from forge_agent import Pipeline, PipelineNode, NodeType, PipelineEngine, AgentContext

pipeline = Pipeline(pipeline_id="stock.v1")

# Parallel scrapers
pipeline.add_node(PipelineNode(
    node_id="price-scraper",
    node_type=NodeType.AGENT,
    agent_id="stock.price_scraper",
    next_nodes=["analyzer"],
))

pipeline.add_node(PipelineNode(
    node_id="news-scraper",
    node_type=NodeType.AGENT,
    agent_id="stock.news_scraper",
    next_nodes=["analyzer"],
))

# Analyzer
pipeline.add_node(PipelineNode(
    node_id="analyzer",
    node_type=NodeType.AGENT,
    agent_id="stock.analyzer",
    next_nodes=["aggregator"],
))

# Final aggregator
pipeline.add_node(PipelineNode(
    node_id="aggregator",
    node_type=NodeType.AGGREGATOR,
))

async def run_stock_analysis():
    ctx = AgentContext(
        scope_id="stock-001",
        scope_name="AAPL",
        config={"symbol": "AAPL"},
    )

    engine = PipelineEngine()
    state = await engine.run(pipeline, ctx)

    board = state["board"]
    print(f"Recommendation: {board.verdict}")
    print(f"Confidence: {board.confidence}")
```
