# Contributing to forge-agent

First off, thanks for taking the time to contribute! 🎉

`forge-agent` is a **community-driven** project. Every contribution — from
a typo fix to a new agent type — matters. This document explains how to
get started, the conventions we follow, and the review process.

---

## 📜 Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are
expected to uphold this code. Please report unacceptable behavior to
[ricky1122alonefe@example.com](mailto:ricky1122alonefe@example.com).

---

## 🐛 Reporting Bugs

Found a bug? Please open an issue using the **Bug Report** template.
Include:

- **Minimal reproduction** (5-line code snippet is best)
- **Expected vs actual behavior**
- **Python version** (`python --version`) and **forge-agent version**
  (`python -c "import forge_agent; print(forge_agent.__version__)"`)
- **Operating system** and any relevant environment details
- **Full traceback** if applicable

> **Security issues**: please **DO NOT** open a public issue. See
> [SECURITY.md](SECURITY.md) for private disclosure.

---

## 💡 Suggesting Features

We welcome feature requests! Use the **Feature Request** template. For
large changes (new core abstractions, breaking changes), please **open
an issue first** to discuss before writing code. This saves everyone
time.

---

## 🛠️ Development Setup

### Prerequisites

- Python **3.10+** (we test against 3.10, 3.11, 3.12)
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- Git

### Fork & Clone

```bash
# 1. Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/forge-agent.git
cd forge-agent

# 2. Add upstream remote
git remote add upstream https://github.com/ricky1122alonefe/forge-agent.git

# 3. Create a feature branch
git checkout -b feat/my-awesome-feature
```

### Install (editable mode)

```bash
# Using uv (recommended — 10x faster)
uv sync --all-extras --dev

# Or using pip
pip install -e ".[dev,llm,mcp,search]"
```

### Verify

```bash
# Run tests
pytest

# Lint
ruff check src tests
ruff format --check src tests

# Type-check
mypy src

# Pre-commit (runs all of the above)
pre-commit run --all-files
```

---

## 📁 Project Structure

```
forge-agent/
├── src/forge_agent/      # Main package (src layout)
│   ├── core/             # Base abstractions (BaseAgent, contracts)
│   ├── registry/         # AgentRegistry
│   ├── scheduler/        # Task execution
│   ├── pipeline/         # DAG orchestration
│   ├── llm/              # Unified LLM layer
│   ├── generator/        # Code generation
│   ├── mcp/              # MCP gateway
│   ├── observability/    # Logging, metrics, events
│   └── cli/              # `forge-agent` command
├── tests/                # unit / integration / e2e
├── docs/                 # mkdocs source
├── examples/             # Reference agent implementations
├── scripts/              # Dev / CI helper scripts
└── pyproject.toml        # Single source of truth for packaging
```

---

## 🎨 Coding Conventions

### Style

- **PEP 8** with `line-length = 100` (enforced by `ruff`)
- **Type hints everywhere** (enforced by `mypy --strict`)
- **Docstrings**: Google style for public APIs
- **Imports**: sorted by `ruff` (isort-compatible)

### Naming

| What | Style | Example |
|---|---|---|
| Classes | `PascalCase` | `BaseAgent`, `AgentContext` |
| Functions / methods | `snake_case` | `observe`, `decide` |
| Constants | `UPPER_SNAKE` | `MAX_RETRIES` |
| Modules | `snake_case` | `agent_report.py` |
| Packages | `snake_case` | `forge_agent` |

### Tests

- **One test file per source file**: `src/foo/bar.py` → `tests/unit/test_bar.py`
- **Naming**: `test_<unit>_<behavior>` (e.g. `test_run_returns_error_report_on_failure`)
- **Use `pytest.mark.asyncio`** for async tests (auto mode is enabled)
- **Coverage**: aim for ≥90% on new code

### Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**: `feat` / `fix` / `docs` / `style` / `refactor` / `test` / `chore` / `perf`

**Examples**:
```
feat(generator): add agent_type field to AgentRequirements
fix(cli): handle missing generated_agents/ directory
docs(readme): add OpenTelemetry badge
```

---

## 🔀 Pull Request Process

1. **Create a feature branch** from `main`
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write code + tests** — PRs without tests will be asked to add them

3. **Update CHANGELOG.md** under `[Unreleased]`:
   ```markdown
   ## [Unreleased]

   ### Added
   - My awesome feature (#123)
   ```

4. **Ensure all checks pass locally**:
   ```bash
   pre-commit run --all-files
   pytest
   ```

5. **Push & open PR**:
   ```bash
   git push origin feat/my-feature
   ```
   Then open a PR on GitHub. The PR template will guide you.

6. **Wait for review** — at least one maintainer approval required

7. **Squash & merge** — we use squash-merge to keep history clean

---

## 🏗️ Architecture Decision Records (ADRs)

For significant design decisions, we write an ADR in `docs/adr/`. Use
[docs/adr/template.md](docs/adr/template.md) as a starting point.

---

## 📚 Documentation

- **Docstrings**: Google style, included in API reference
- **User docs**: `docs/` (mkdocs), built & deployed on merge to `main`
- **Examples**: `examples/` for end-to-end demos

When you add a new public API, please add a docstring AND a section in
the relevant `docs/guides/` page.

---

## 🌍 Translations

Currently English-only. We welcome translations of the docs in
[docs/i18n/](docs/i18n/) — open an issue first to coordinate.

---

## 🙋 Getting Help

- **GitHub Discussions**: for questions and ideas
- **GitHub Issues**: for bugs and feature requests
- **Email**: [ricky1122alonefe@example.com](mailto:ricky1122alonefe@example.com) for private matters

---

## 📜 License

By contributing, you agree that your contributions will be licensed
under the [MIT License](LICENSE).
