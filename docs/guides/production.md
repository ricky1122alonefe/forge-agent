# Production Checklist

Prepare your agents for production deployment.

## Code Quality

### Testing

- [ ] Unit tests for all lifecycle methods
- [ ] Integration tests for pipelines
- [ ] End-to-end tests for critical paths
- [ ] Error handling tests
- [ ] Performance tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=forge_agent --cov-report=term-missing
```

### Type Safety

- [ ] All methods have type hints
- [ ] mypy passes with strict mode
- [ ] No `Any` types in public API

```bash
mypy src/forge_agent
```

### Documentation

- [ ] All classes have docstrings
- [ ] All public methods documented
- [ ] Examples provided
- [ ] README updated

## Configuration

### Environment

- [ ] Python 3.10+ installed
- [ ] Virtual environment configured
- [ ] Dependencies pinned
- [ ] Security updates applied

```bash
python --version  # >= 3.10
pip install -r requirements.txt
```

### LLM Providers

- [ ] Primary provider configured
- [ ] Fallback providers set
- [ ] API keys in environment variables
- [ ] Rate limits understood

```bash
export FORGE_LLM_PRIMARY=openai
export OPENAI_API_KEY=sk-...
```

### MCP Servers

- [ ] Required servers running
- [ ] Connection URLs configured
- [ ] Authentication set up
- [ ] Policies defined

## Monitoring

### Logging

- [ ] Structured logging enabled
- [ ] Log level appropriate (INFO for prod)
- [ ] Log aggregation configured
- [ ] Sensitive data filtered

```python
from forge_agent.observability import configure_logging

configure_logging(level="INFO", json_output=True)
```

### Tracing

- [ ] Trace collection enabled
- [ ] OTel exporter configured
- [ ] Trace retention policy set
- [ ] Performance baselines established

```python
from forge_agent.observability import install_otel_exporter

install_otel_exporter(service_name="my-agents")
```

### Metrics

- [ ] Key metrics identified
- [ ] Collection implemented
- [ ] Dashboards created
- [ ] Alerts configured

## Security

### Sandboxing

- [ ] Sandbox enabled for generated code
- [ ] Resource limits set (CPU, memory, time)
- [ ] Network access restricted
- [ ] File system access controlled

```python
from forge_agent.generator.sandbox import SandboxRunner

sandbox = SandboxRunner(
    timeout=30,
    memory_limit="512M",
    network_access=False,
)
```

### Input Validation

- [ ] All inputs validated
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] Command injection prevented

### Secrets Management

- [ ] No secrets in code
- [ ] Environment variables used
- [ ] Secret rotation planned
- [ ] Access logs enabled

## Performance

### Optimization

- [ ] Connection pooling enabled
- [ ] Caching implemented
- [ ] Batch processing used
- [ ] Async/await properly used

### Resource Management

- [ ] Memory usage monitored
- [ ] CPU usage optimized
- [ ] Disk I/O minimized
- [ ] Network calls batched

### Scalability

- [ ] Horizontal scaling tested
- [ ] Load balancing configured
- [ ] Database connections pooled
- [ ] Queue system implemented

## Deployment

### Containerization

- [ ] Dockerfile created
- [ ] Image size optimized
- [ ] Security scanning passed
- [ ] Health checks added

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY generated_agents/ ./generated_agents/

HEALTHCHECK CMD python healthcheck.py
CMD ["python", "main.py"]
```

### CI/CD

- [ ] Automated tests in CI
- [ ] Code quality checks
- [ ] Security scanning
- [ ] Automated deployment
- [ ] Rollback procedure tested

### Infrastructure

- [ ] Load balancer configured
- [ ] Auto-scaling enabled
- [ ] Backup strategy defined
- [ ] Disaster recovery tested

## Operations

### Runbooks

- [ ] Deployment runbook
- [ ] Rollback runbook
- [ ] Incident response plan
- [ ] On-call rotation defined

### Documentation

- [ ] Architecture documented
- [ ] API documentation published
- [ ] Troubleshooting guide
- [ ] FAQ maintained

### Training

- [ ] Team trained on system
- [ ] Documentation accessible
- [ ] Support channels defined
- [ ] Escalation paths clear

## Pre-Launch Checklist

### Final Checks

- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Security audit passed
- [ ] Documentation complete
- [ ] Stakeholders approved

### Launch Day

- [ ] Monitoring active
- [ ] Alerts configured
- [ ] Team on standby
- [ ] Rollback plan ready
- [ ] Communication plan active

### Post-Launch

- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Review user feedback
- [ ] Update documentation
- [ ] Conduct retrospective

## Monitoring Dashboard

Key metrics to track:

1. **Request rate** — Requests per second
2. **Error rate** — Percentage of failed requests
3. **Latency** — P50, P95, P99 response times
4. **Token usage** — LLM token consumption
5. **Cost** — Daily/weekly/monthly costs
6. **Agent health** — Success/failure rates per agent
7. **Pipeline health** — End-to-end success rates
8. **Resource usage** — CPU, memory, disk

## Incident Response

### Severity Levels

- **P0** — System down, immediate response
- **P1** — Major feature broken, 1 hour response
- **P2** — Minor issue, 4 hour response
- **P3** — Cosmetic issue, next business day

### Response Process

1. **Detect** — Monitoring alerts
2. **Triage** — Assess severity
3. **Mitigate** — Quick fix or rollback
4. **Resolve** — Permanent fix
5. **Review** — Post-mortem

## Best Practices

1. **Start small** — Deploy to staging first
2. **Monitor everything** — You can't fix what you can't see
3. **Automate** — Reduce human error
4. **Document** — Future you will thank present you
5. **Test failures** — Know how your system breaks
