# Football Match Agent (v2) — Example

This example demonstrates **migrating** a legacy Agent from the `guess_you_like`
project (`match_agents/experts.py:intel_agent`) to the **forge-agent** v2 contract.

## What changed vs. the original

| Aspect | Original (v1) | Forge-Agent v2 |
|---|---|---|
| Inherits from | (free function) | `BaseAgent` |
| Registration | `match_agents/profiles.py:AGENT_REGISTRY` dict | `@register_agent` decorator |
| Input | `(prediction, index, output_root)` positional args | `AgentContext` (structured) |
| Output | `AgentReport` dataclass | **Same** `AgentReport` (extended) |
| Logging | `print` / ad-hoc | `self.log(...)` via `LoggerProtocol` |
| Search | `match_agents/web_lookup.py` direct call | `self.search(...)` via `SearcherProtocol` |
| Prompt | Hard-coded `ai_prompt.py` | `self.prompt_manager.render(...)` (versioned) |
| Learning | None | `reflect()` + `learn()` (default impls) |
| Pipeline | `match_agents/pipeline_config.py` | `forge_agent.pipeline.Pipeline` (DAG) |
| Self-iteration | None | `evolve()` (v0.4+) |

## Run

```bash
cd forge-agent
pip install -e ".[dev]"
python -m examples.football_match_agent.demo
```

## Files

- `agents.py`       — `FootballIntelAgent` (BaseAgent subclass)
- `pipeline.py`     — sample DAG wiring football → chief
- `demo.py`         — runnable end-to-end demo
