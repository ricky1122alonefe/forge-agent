# Contributing

Thank you for your interest in contributing to forge-agent!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/forge-agent.git`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Install pre-commit hooks: `pre-commit install`
5. Create a branch: `git checkout -b feature/my-feature`

## Development Setup

```bash
# Clone and install
git clone https://github.com/ricky1122alonefe/forge-agent.git
cd forge-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest

# Run with coverage
pytest --cov=forge_agent --cov-report=term-missing

# Type check
mypy src/forge_agent

# Lint
ruff check src/ tests/
```

## Code Style

- Follow PEP 8
- Use type hints everywhere
- Write docstrings (Google style)
- Keep functions focused and small
- Add tests for new functionality

## Pull Request Process

1. Update documentation for any changed behavior
2. Add tests for new functionality
3. Ensure all tests pass: `pytest`
4. Ensure type checking passes: `mypy`
5. Ensure linting passes: `ruff check`
6. Submit a pull request

## Reporting Bugs

Open an issue with:

- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Minimal code example

## Feature Requests

Open an issue with:

- Description of the feature
- Use case / motivation
- Proposed API (if applicable)
- Alternatives considered

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Accept constructive criticism gracefully
- Prioritize the community's well-being

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
