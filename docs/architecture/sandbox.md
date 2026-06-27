# Sandboxing

forge-agent sandboxes all generated code to prevent security issues and resource abuse.

## Overview

When an agent is generated, it's tested in an isolated subprocess before being saved:

```python
from forge_agent.generator.sandbox import SandboxRunner

sandbox = SandboxRunner(
    timeout=30,           # seconds
    memory_limit="512M",  # max memory
    network_access=False, # disable network
)

result = await sandbox.run(code)

if result.success:
    print("Code is safe!")
else:
    print(f"Code failed: {result.stderr}")
```

## Security Model

### Process Isolation

- Each execution runs in a separate subprocess
- No shared memory with parent process
- Separate file descriptors
- Isolated environment variables

### Resource Limits

```python
sandbox = SandboxRunner(
    timeout=30,           # Kill after 30 seconds
    memory_limit="512M",  # Max 512MB RAM
    cpu_limit=1.0,        # Max 1 CPU core
    network_access=False, # No network
)
```

### Import Restrictions

Only whitelisted modules can be imported:

```python
ALLOWED_MODULES = [
    "asyncio",
    "datetime",
    "json",
    "typing",
    "forge_agent",
    # ... more safe modules
]
```

## Validation Pipeline

Before sandboxing, code goes through:

### 1. Syntax Check

```python
import ast

try:
    ast.parse(code)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
```

### 2. Type Check

```python
# Run mypy on generated code
result = subprocess.run(
    ["mypy", "--strict", "generated_code.py"],
    capture_output=True,
)
```

### 3. Security Scan

```python
# Run bandit security scanner
result = subprocess.run(
    ["bandit", "-r", "generated_code.py"],
    capture_output=True,
)
```

### 4. Sandbox Execution

```python
result = await sandbox.run(code)
```

## Sandbox Result

```python
@dataclass
class SandboxResult:
    success: bool
    stdout: str
    stderr: str
    duration_ms: float
    memory_used: int
    exit_code: int
```

## Configuration

### Environment Variables

```bash
# Disable sandbox (development only!)
export FORGE_SANDBOX_DISABLED=true

# Increase timeout
export FORGE_SANDBOX_TIMEOUT=60

# Enable network access
export FORGE_SANDBOX_NETWORK=true
```

### Per-Agent Configuration

```python
from forge_agent.generator.sandbox import SandboxConfig

config = SandboxConfig(
    timeout=60,
    memory_limit="1G",
    network_access=True,
    allowed_modules=["requests", "pandas"],
)

sandbox = SandboxRunner(config=config)
```

## Best Practices

1. **Always sandbox** — Never run untrusted code without sandboxing
2. **Set appropriate limits** — Balance security with functionality
3. **Monitor resource usage** — Track memory and CPU consumption
4. **Log sandbox results** — Keep audit trail
5. **Review failures** — Investigate all sandbox failures

## Example: Custom Sandbox

```python
from forge_agent.generator.sandbox import SandboxRunner, SandboxConfig

# Create custom config
config = SandboxConfig(
    timeout=120,
    memory_limit="2G",
    network_access=True,
    allowed_modules=[
        "requests",
        "pandas",
        "numpy",
        "forge_agent",
    ],
    env_vars={
        "API_KEY": "test-key",
    },
)

# Create sandbox
sandbox = SandboxRunner(config=config)

# Run code
result = await sandbox.run(generated_code)

if result.success:
    print(f"✓ Code passed in {result.duration_ms}ms")
    print(f"  Memory: {result.memory_used / 1024 / 1024:.2f} MB")
else:
    print(f"✗ Code failed:")
    print(result.stderr)
```

## Troubleshooting

### Timeout Errors

Increase timeout:

```python
sandbox = SandboxRunner(timeout=120)
```

### Memory Errors

Increase memory limit:

```python
sandbox = SandboxRunner(memory_limit="2G")
```

### Import Errors

Add module to whitelist:

```python
config = SandboxConfig(allowed_modules=["my_module"])
```

### Network Errors

Enable network access:

```python
sandbox = SandboxRunner(network_access=True)
```
