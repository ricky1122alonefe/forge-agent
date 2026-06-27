# MCP (Model Context Protocol)

MCP provides a standardized way for agents to interact with external tools and services.

## Overview

forge-agent has first-class MCP support:

- Connect to MCP servers
- Call MCP tools
- Register MCP tools in the gateway
- Generate agents with MCP capabilities

## Connecting to MCP Servers

```python
from forge_agent.mcp import MCPClient

client = MCPClient()

# Connect to a server
await client.connect("http://localhost:3000")

# List available tools
tools = await client.list_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")
```

## Calling MCP Tools

```python
# Call a tool
result = await client.call_tool("read_file", {
    "path": "/data/config.json"
})

print(result.content)
```

## MCP Gateway

The gateway manages MCP tool policies and access control:

```python
from forge_agent.mcp import MCPGateway

gateway = MCPGateway()

# Register a tool with policy
gateway.set_policy("read_file", allowed=True, rate_limit=10)
gateway.set_policy("write_file", allowed=False)

# Call through gateway
result = await gateway.call("read_file", {"path": "/data/config.json"})
```

## Using MCP in Agents

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict
from forge_agent.mcp import MCPClient

@register_agent(domain="filesystem", tags=["mcp", "files"])
class FileSystemAgent(BaseAgent):
    agent_id = "fs.reader"
    name = "File System Agent"
    domain = "filesystem"

    def __init__(self):
        super().__init__()
        self.mcp_client = MCPClient()

    async def observe(self, ctx: AgentContext) -> dict:
        # Connect to MCP server
        await self.mcp_client.connect("http://localhost:3000")

        # Read file via MCP
        path = ctx.config.get("path", "/data/input.txt")
        result = await self.mcp_client.call_tool("read_file", {"path": path})

        return {"content": result.content}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        content = observation["content"]
        lines = content.split("\n")
        return {"line_count": len(lines)}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[f"Read {decision['line_count']} lines"],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Generating Agents with MCP

```bash
# Generate with MCP tools
forge-agent generate "read configuration files" --mcp-tools=filesystem

# The generated agent will include MCP client code
```

## MCP Server Examples

### Filesystem Server

```bash
# Start MCP filesystem server
npx @modelcontextprotocol/server-filesystem /path/to/data
```

### Fetch Server

```bash
# Start MCP fetch server
npx @modelcontextprotocol/server-fetch
```

## Error Handling

```python
from forge_agent.exceptions import MCPToolCallError, MCPNotConnectedError

try:
    result = await client.call_tool("risky_tool", {})
except MCPNotConnectedError:
    print("Not connected to MCP server")
except MCPToolCallError as e:
    print(f"Tool call failed: {e}")
```

## Best Practices

1. **Connect once, reuse** — Keep MCP connections alive
2. **Handle errors** — MCP calls can fail
3. **Use gateway** — Centralize policy management
4. **Validate inputs** — Sanitize data before passing to MCP
5. **Monitor usage** — Track MCP tool calls in traces
