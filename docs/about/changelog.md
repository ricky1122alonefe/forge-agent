# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-27

### Added

- **Agent Types**: SCRAPER, ANALYZER, MONITOR, GENERATOR, CUSTOM
- **Dataset Module**: LocalDatasetStore, SqliteDatasetStore, registry
- **MCP Integration**: MCPClient, MCPGateway, policy management
- **Self-Iteration**: Learning optimizer, evolve() method
- **Observability**: Trace/Span system, Judge module, structured logging
- **Prompt System**: PromptProvider protocol, file-based prompts
- **Pipeline Enhancements**: Conditional edges, parallel execution
- **Token Tracking**: Cost calculation per agent run
- **forge-agent new**: 5 project templates (basic, stock, football, social, office)
- **forge-agent doctor**: Environment health check command
- **Error Messages**: ForgeError hierarchy with user-friendly hints
- **Pydantic Validation**: Non-breaking validation layer
- **OpenTelemetry**: OTel exporter adapter for distributed tracing
- **mkdocs**: Documentation site with Material theme

### Changed

- Improved code generation prompts for all agent types
- Enhanced sandbox security model
- Better error handling throughout

### Fixed

- Pipeline aggregation edge cases
- MCP connection lifecycle issues
- Version rollback consistency

## [0.2.0] - 2026-06-26

### Added

- CodeStore with versioning
- MANIFEST.json for generated agents
- Basic CLI commands (list, activate, rollback)
- LLM provider abstraction (OpenAI, Anthropic, Mock)

## [0.1.0] - 2026-06-25

### Added

- Initial release
- BaseAgent with lifecycle contract
- AgentContext and AgentReport
- Basic pipeline support
- Registry and scheduler
