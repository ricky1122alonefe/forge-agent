# Changelog

All notable changes to forge-agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-27

### Added
- Unified logging system (structlog + contextvars)
- `forge-agent logs` command (tail/follow/json)
- Auto inject agent_id / run_id / domain to contextvars
- Dual renderer: dev console / prod JSON (FORGE_LOG_JSON=1)
- stdlib bridge: third-party library logs go through unified format
- Async task isolation: concurrent agents don't cross-pollute contextvars
- 19 new tests (contextvars / dual renderer / concurrent isolation / agent integration)

### Changed
- `StdLogger` refactored to structlog-backed thin adapter
- `BaseAgent.run()` auto-binds contextvars

## [0.2.0] - 2026-06-XX

### Added
- LLM-driven code generator (4 layers: secrets/config/protocol/registry)
- 5 LLM providers: OpenAI, Anthropic, Gemini, Ollama, Mock
- CodeStore with versioning (v1/v2/...)
- MANIFEST.json atomic write + file lock
- 15 CLI commands
- Sandbox module
- 40 tests passing

## [0.1.0] - 2026-06-XX

### Added
- BaseAgent strong contract (3 must-implement + 5 optional capabilities)
- 5 capabilities: log / search / memory / reflect / prompt_manager
- AgentRegistry singleton
- Scheduler (sequential/parallel/priority strategies)
- Pipeline DAG orchestration
- 16 tests passing

[Unreleased]: https://github.com/ricky1122alonefe/forge-agent/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ricky1122alonefe/forge-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ricky1122alonefe/forge-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ricky1122alonefe/forge-agent/releases/tag/v0.1.0
