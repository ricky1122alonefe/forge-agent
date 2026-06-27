"""`forge-agent new` — create a new project from a template.

For v0.2 this is a stub: it just creates a minimal pyproject.toml + agent file.
Templates will be filled in v0.3.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("new", help="Create a new project from a template")
    p.add_argument("name", help="Project name")
    p.add_argument("--template", "-t", default="basic",
                   choices=["basic", "stock", "football", "social", "office"],
                   help="Template to use (default: basic)")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    target = args.project / args.name
    if target.exists():
        print(f"Error: {target} already exists.")
        return 1
    target.mkdir(parents=True)
    (target / "agents").mkdir()
    (target / "pipelines").mkdir()
    (target / "tests").mkdir()
    (target / "generated_agents").mkdir()
    (target / "generated_agents" / ".gitkeep").touch()

    # Minimal pyproject.toml
    (target / "pyproject.toml").write_text(
        f"""[project]
name = "{args.name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "forge-agent @ file://{Path(__file__).resolve().parents[3]}/..",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
""",
        encoding="utf-8",
    )

    # Example agent
    (target / "agents" / "__init__.py").touch()
    (target / "agents" / "example.py").write_text(
        f'''"""Example agent scaffold."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="{args.template}")
class ExampleAgent(BaseAgent):
    agent_id = "{args.template}.example"
    name = "Example Agent"

    async def observe(self, ctx: AgentContext) -> dict:
        return {{"raw": ctx.payload}}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {{"strategy": "echo"}}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[f"observed: {{observation}}"],
            run_id=ctx.run_id,
        )
''',
        encoding="utf-8",
    )

    (target / "README.md").write_text(
        f"# {args.name}\n\nCreated with `forge-agent new {args.name} --template={args.template}`.\n",
        encoding="utf-8",
    )

    print(f"✓ Created {target}/")
    print(f"\nNext steps:")
    print(f"  cd {target}")
    print(f"  pip install -e .")
    print(f"  forge-agent llm list")
    print(f"  forge-agent generate \"...\"")
    return 0
