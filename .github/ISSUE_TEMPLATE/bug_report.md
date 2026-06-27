---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## To Reproduce

Steps to reproduce the behavior:

1. Install forge-agent via `...`
2. Run the following code: `...`
3. See error

## Minimal Reproduction

```python
# Paste the smallest possible code that reproduces the bug
import forge_agent
# ...
```

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

What actually happened. Include the full traceback:

```
Traceback (most recent call last):
  ...
```

## Environment

- **OS**: [e.g. macOS 14.4, Ubuntu 22.04, Windows 11]
- **Python version**: [e.g. 3.11.7 — output of `python --version`]
- **forge-agent version**: [e.g. 0.3.0 — output of `python -c "import forge_agent; print(forge_agent.__version__)"`]
- **LLM provider** (if relevant): [e.g. openai, anthropic, ollama]
- **Installation method**: [e.g. `pip install -e .`, `uv sync`, `pip install forge-agent`]

## Additional Context

- Any logs (`FORGE_LOG_JSON=1 forge-agent ... 2> log.jsonl`)
- Screenshots (if UI-related)
- Related issues or PRs

## Checklist

- [ ] I have searched [existing issues](https://github.com/ricky1122alonefe/forge-agent/issues) for duplicates
- [ ] I have tested with the latest version
- [ ] I have included a minimal reproduction
- [ ] I have included the full traceback
