# Security

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue.**

Instead, email: security@forge-agent.dev

Include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Model

### Sandboxing

All generated code runs in isolated subprocesses with:

- Resource limits (CPU, memory, time)
- Network access restrictions
- File system access control
- Import whitelisting

### Validation

Generated code goes through:

1. Syntax checking (ast.parse)
2. Type checking (mypy)
3. Security scanning (bandit)
4. Sandboxed execution

### Best Practices

When using forge-agent in production:

1. **Keep sandbox enabled** — Never disable in production
2. **Review generated code** — Inspect before deploying
3. **Limit permissions** — Use least-privilege principle
4. **Monitor execution** — Track resource usage and errors
5. **Update regularly** — Keep dependencies up to date

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| 0.2.x   | Yes       |
| 0.1.x   | No        |

## Security Updates

Security updates are released as patch versions (e.g., 0.3.1).

Subscribe to GitHub releases to be notified of security updates.
