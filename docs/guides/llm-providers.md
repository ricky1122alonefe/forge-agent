# Use LLM Providers

Configure and use different LLM providers with forge-agent.

## Supported Providers

- **OpenAI** — GPT-4, GPT-3.5
- **Anthropic** — Claude 3
- **Google** — Gemini
- **Ollama** — Local models
- **Mock** — Testing

## Configuration

### Environment Variables

```bash
# Set primary provider
export FORGE_LLM_PRIMARY=openai

# API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...

# Optional: Custom endpoints
export OPENAI_BASE_URL=https://api.openai.com/v1
export ANTHROPIC_BASE_URL=https://api.anthropic.com
```

### Configuration File

Create `llm_config.json`:

```json
{
  "primary": "openai",
  "providers": {
    "openai": {
      "model": "gpt-4",
      "temperature": 0.7,
      "max_tokens": 2000
    },
    "anthropic": {
      "model": "claude-3-opus",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }
}
```

## Using LLM in Agents

### Basic Usage

```python
from forge_agent.llm import chat

async def generate_text(prompt: str) -> str:
    response = await chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.content
```

### In an Agent

```python
from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent, Verdict
from forge_agent.llm import chat

@register_agent(domain="writer", tags=["llm"])
class WriterAgent(BaseAgent):
    agent_id = "writer.basic"
    name = "Writer Agent"
    domain = "writer"

    async def observe(self, ctx: AgentContext) -> dict:
        topic = ctx.config.get("topic", "AI")
        return {"topic": topic}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        topic = observation["topic"]

        response = await chat(
            messages=[
                {"role": "system", "content": "You are a helpful writer."},
                {"role": "user", "content": f"Write about {topic}"},
            ],
            temperature=0.7,
        )

        return {"content": response.content}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[decision["content"]],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```

## Provider-Specific Features

### OpenAI

```python
from forge_agent.llm.providers.openai import OpenAIClient

client = OpenAIClient(
    model="gpt-4",
    temperature=0.7,
    max_tokens=2000,
)

response = await client.chat(messages=[...])
```

### Anthropic

```python
from forge_agent.llm.providers.anthropic import AnthropicClient

client = AnthropicClient(
    model="claude-3-opus",
    temperature=0.7,
    max_tokens=2000,
)

response = await client.chat(messages=[...])
```

### Ollama (Local)

```python
from forge_agent.llm.providers.ollama import OllamaClient

client = OllamaClient(
    model="llama2",
    base_url="http://localhost:11434",
)

response = await client.chat(messages=[...])
```

## Token Tracking

```python
from forge_agent.llm import chat

response = await chat(messages=[...])

print(f"Tokens in: {response.tokens_in}")
print(f"Tokens out: {response.tokens_out}")
print(f"Cost: ${response.cost:.4f}")
```

## Fallback Providers

```python
from forge_agent.llm import chat_with_fallback

response = await chat_with_fallback(
    messages=[...],
    providers=["openai", "anthropic", "ollama"],
)
```

## Best Practices

1. **Set temperature appropriately** — Lower for factual, higher for creative
2. **Use system prompts** — Guide the model's behavior
3. **Track costs** — Monitor token usage
4. **Implement retries** — Handle rate limits
5. **Cache responses** — Avoid redundant calls

## Example: Multi-Provider Agent

```python
@register_agent(domain="research", tags=["multi-llm"])
class ResearchAgent(BaseAgent):
    agent_id = "research.multi"
    name = "Research Agent"
    domain = "research"

    async def observe(self, ctx: AgentContext) -> dict:
        query = ctx.config.get("query")

        # Use different providers for different tasks
        summary = await chat(
            messages=[{"role": "user", "content": f"Summarize: {query}"}],
            provider="openai",
        )

        analysis = await chat(
            messages=[{"role": "user", "content": f"Analyze: {query}"}],
            provider="anthropic",
        )

        return {
            "summary": summary.content,
            "analysis": analysis.content,
        }

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {
            "summary": observation["summary"],
            "analysis": observation["analysis"],
        }

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.POSITIVE,
            evidence=[decision["summary"], decision["analysis"]],
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
        )
```
