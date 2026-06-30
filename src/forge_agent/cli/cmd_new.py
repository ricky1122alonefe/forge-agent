"""`forge-agent new` — create a new project from a template.

Each template generates a domain-specific scaffold with:
    - Tailored example agent(s)
    - Relevant dependencies
    - Domain-specific README
    - Pipeline example (where applicable)

Projects are created under a tenant namespace, enabling both single-tenant
and multi-tenant deployments.

Templates:
    config-driven — low-code/no-code scaffold with YAML agents and pipelines
    basic         — minimal scaffold, generic agent
    stock         — stock market monitoring (scraper + analyzer)
    football      — sports data tracking (scraper + monitor)
    social        — social media analysis (scraper + generator)
    office        — office automation (monitor + generator)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from forge_agent.platform import LocalTenant


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("new", help="Create a new project from a template")
    p.add_argument("name", help="Project name")
    p.add_argument(
        "--template",
        "-t",
        default="config-driven",
        choices=["config-driven", "basic", "stock", "football", "social", "office"],
        help="Template to use (default: config-driven)",
    )
    p.add_argument(
        "--tenant",
        default="default",
        help="Tenant id for project isolation (default: default)",
    )
    p.set_defaults(func=run)


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "config-driven": {
        "description": "Low-code/no-code scaffold: YAML agents, pipelines, and built-in tools",
        "domain": "generic",
        "extra_deps": ["pyyaml"],
        "agents": [],
        "readme_extra": (
            "Low-code / no-code project scaffold.\n\n"
            "Define agents in `agents/*.yaml`, pipelines in `pipelines/*.yaml`, "
            "and run with `python run.py`.\n\n"
            "To add a built-in capability, edit the YAML files; no Python code is required.\n"
        ),
    },
    "basic": {
        "description": "Minimal scaffold with a generic agent",
        "domain": "generic",
        "extra_deps": [],
        "agents": [
            {
                "filename": "example.py",
                "class_name": "ExampleAgent",
                "agent_id": "generic.example",
                "name": "Example Agent",
                "code": '''"""Example agent scaffold — a minimal echo agent."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="generic")
class ExampleAgent(BaseAgent):
    agent_id = "generic.example"
    name = "Example Agent"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"raw": ctx.payload}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"strategy": "echo"}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[f"observed: {observation}"],
            run_id=ctx.run_id,
        )
''',
            },
        ],
        "readme_extra": "A generic forge-agent project. Customize agents/ to build your own.",
    },
    "stock": {
        "description": "Stock market monitoring with scraper + analyzer",
        "domain": "finance",
        "extra_deps": ["requests", "pandas"],
        "agents": [
            {
                "filename": "stock_scraper.py",
                "class_name": "StockScraperAgent",
                "agent_id": "finance.stock_scraper",
                "name": "Stock Price Scraper",
                "code": '''"""Stock price scraper agent — fetches real-time stock data."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="finance")
class StockScraperAgent(BaseAgent):
    agent_id = "finance.stock_scraper"
    name = "Stock Price Scraper"

    async def observe(self, ctx: AgentContext) -> dict:
        symbols = ctx.payload.get("symbols", ["AAPL", "GOOGL"])
        # TODO: Replace with real API call (e.g. Yahoo Finance, Alpha Vantage)
        prices = {s: {"price": 0.0, "change": 0.0} for s in symbols}
        return {"symbols": symbols, "prices": prices}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {"action": "report", "data": observation}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        prices = decision.get("data", {}).get("prices", {})
        evidence = [f"{s}: ${p['price']:.2f} ({p['change']:+.2f}%)" for s, p in prices.items()]
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=evidence,
            run_id=ctx.run_id,
        )
''',
            },
            {
                "filename": "stock_analyzer.py",
                "class_name": "StockAnalyzerAgent",
                "agent_id": "finance.stock_analyzer",
                "name": "Stock Trend Analyzer",
                "code": '''"""Stock trend analyzer — analyzes price movements and generates insights."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="finance")
class StockAnalyzerAgent(BaseAgent):
    agent_id = "finance.stock_analyzer"
    name = "Stock Trend Analyzer"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"price_history": ctx.payload.get("price_history", [])}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        history = observation.get("price_history", [])
        if len(history) < 2:
            return {"trend": "insufficient_data", "signal": "hold"}
        # Simple trend detection
        recent = history[-5:] if len(history) >= 5 else history
        avg = sum(p.get("price", 0) for p in recent) / len(recent)
        last = recent[-1].get("price", 0)
        if last > avg * 1.02:
            signal = "buy"
        elif last < avg * 0.98:
            signal = "sell"
        else:
            signal = "hold"
        return {"trend": "analyzed", "signal": signal, "avg_price": avg}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[f"Signal: {decision['signal']}", f"Avg: ${decision.get('avg_price', 0):.2f}"],
            run_id=ctx.run_id,
        )
''',
            },
        ],
        "readme_extra": (
            "Stock market monitoring project.\n\n"
            "Agents:\n"
            "- **StockScraperAgent**: Fetches real-time stock prices\n"
            "- **StockAnalyzerAgent**: Analyzes trends and generates signals\n"
        ),
    },
    "football": {
        "description": "Sports data tracking with scraper + monitor",
        "domain": "sports",
        "extra_deps": ["requests"],
        "agents": [
            {
                "filename": "match_scraper.py",
                "class_name": "MatchScraperAgent",
                "agent_id": "sports.match_scraper",
                "name": "Match Data Scraper",
                "code": '''"""Match data scraper — fetches football match results and stats."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="sports")
class MatchScraperAgent(BaseAgent):
    agent_id = "sports.match_scraper"
    name = "Match Data Scraper"

    async def observe(self, ctx: AgentContext) -> dict:
        league = ctx.payload.get("league", "premier_league")
        # TODO: Replace with real API (e.g. football-data.org)
        matches = [
            {"home": "Team A", "away": "Team B", "score": "2-1", "status": "finished"},
        ]
        return {"league": league, "matches": matches}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        finished = [m for m in observation.get("matches", []) if m.get("status") == "finished"]
        return {"action": "report_results", "matches": finished}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        evidence = [
            f"{m['home']} vs {m['away']}: {m['score']}"
            for m in decision.get("matches", [])
        ]
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=evidence or ["No finished matches"],
            run_id=ctx.run_id,
        )
''',
            },
            {
                "filename": "match_monitor.py",
                "class_name": "MatchMonitorAgent",
                "agent_id": "sports.match_monitor",
                "name": "Match Monitor",
                "code": '''"""Match monitor — watches for live score changes and alerts."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="sports")
class MatchMonitorAgent(BaseAgent):
    agent_id = "sports.match_monitor"
    name = "Match Monitor"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"live_matches": ctx.payload.get("live_matches", [])}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        live = observation.get("live_matches", [])
        alerts = []
        for match in live:
            if match.get("event") == "goal":
                alerts.append(f"GOAL! {match.get('team', '?')} scored!")
        return {"alerts": alerts}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        alerts = decision.get("alerts", [])
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=alerts or ["No live events"],
            run_id=ctx.run_id,
        )
''',
            },
        ],
        "readme_extra": (
            "Sports data tracking project.\n\n"
            "Agents:\n"
            "- **MatchScraperAgent**: Fetches match results and statistics\n"
            "- **MatchMonitorAgent**: Monitors live matches for score changes\n"
        ),
    },
    "social": {
        "description": "Social media analysis with scraper + generator",
        "domain": "social",
        "extra_deps": ["requests"],
        "agents": [
            {
                "filename": "social_scraper.py",
                "class_name": "SocialScraperAgent",
                "agent_id": "social.scraper",
                "name": "Social Media Scraper",
                "code": '''"""Social media scraper — collects posts and engagement data."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="social")
class SocialScraperAgent(BaseAgent):
    agent_id = "social.scraper"
    name = "Social Media Scraper"

    async def observe(self, ctx: AgentContext) -> dict:
        platform = ctx.payload.get("platform", "twitter")
        query = ctx.payload.get("query", "forge-agent")
        # TODO: Replace with real API (Twitter API, Reddit API, etc.)
        posts = [
            {"text": f"Sample post about {query}", "likes": 42, "shares": 7},
        ]
        return {"platform": platform, "query": query, "posts": posts}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        posts = observation.get("posts", [])
        total_engagement = sum(p.get("likes", 0) + p.get("shares", 0) for p in posts)
        return {"action": "analyze", "total_engagement": total_engagement, "post_count": len(posts)}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[
                f"Collected {decision['post_count']} posts",
                f"Total engagement: {decision['total_engagement']}",
            ],
            run_id=ctx.run_id,
        )
''',
            },
            {
                "filename": "content_generator.py",
                "class_name": "ContentGeneratorAgent",
                "agent_id": "social.generator",
                "name": "Content Generator",
                "code": '''"""Content generator — creates social media content based on trends."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="social")
class ContentGeneratorAgent(BaseAgent):
    agent_id = "social.generator"
    name = "Content Generator"

    async def observe(self, ctx: AgentContext) -> dict:
        return {
            "trending_topics": ctx.payload.get("trending_topics", []),
            "tone": ctx.payload.get("tone", "professional"),
        }

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        topics = observation.get("trending_topics", [])
        tone = observation.get("tone", "professional")
        # TODO: Integrate with LLM for real content generation
        draft = f"Draft post about {', '.join(topics[:3])} in {tone} tone"
        return {"draft": draft, "topics_used": topics[:3]}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[f"Generated: {decision['draft']}"],
            run_id=ctx.run_id,
        )
''',
            },
        ],
        "readme_extra": (
            "Social media analysis project.\n\n"
            "Agents:\n"
            "- **SocialScraperAgent**: Collects posts and engagement data\n"
            "- **ContentGeneratorAgent**: Generates content based on trending topics\n"
        ),
    },
    "office": {
        "description": "Office automation with monitor + generator",
        "domain": "office",
        "extra_deps": [],
        "agents": [
            {
                "filename": "task_monitor.py",
                "class_name": "TaskMonitorAgent",
                "agent_id": "office.task_monitor",
                "name": "Task Monitor",
                "code": '''"""Task monitor — tracks project tasks and deadlines."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="office")
class TaskMonitorAgent(BaseAgent):
    agent_id = "office.task_monitor"
    name = "Task Monitor"

    async def observe(self, ctx: AgentContext) -> dict:
        tasks = ctx.payload.get("tasks", [])
        # Check for overdue tasks
        overdue = [t for t in tasks if t.get("status") == "overdue"]
        return {"total_tasks": len(tasks), "overdue": overdue}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        overdue = observation.get("overdue", [])
        if overdue:
            return {"action": "alert", "overdue_count": len(overdue), "tasks": overdue}
        return {"action": "all_clear", "overdue_count": 0}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        if decision["action"] == "alert":
            evidence = [f"⚠ {decision['overdue_count']} overdue task(s)"]
            for t in decision.get("tasks", []):
                evidence.append(f"  - {t.get('name', 'unnamed')}: due {t.get('due', 'unknown')}")
        else:
            evidence = ["All tasks on track"]
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=evidence,
            run_id=ctx.run_id,
        )
''',
            },
            {
                "filename": "report_generator.py",
                "class_name": "ReportGeneratorAgent",
                "agent_id": "office.report_generator",
                "name": "Report Generator",
                "code": '''"""Report generator — creates weekly summaries and status reports."""

from forge_agent import BaseAgent, AgentContext, AgentReport, register_agent


@register_agent(domain="office")
class ReportGeneratorAgent(BaseAgent):
    agent_id = "office.report_generator"
    name = "Report Generator"

    async def observe(self, ctx: AgentContext) -> dict:
        return {
            "completed_tasks": ctx.payload.get("completed_tasks", []),
            "period": ctx.payload.get("period", "this week"),
        }

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        completed = observation.get("completed_tasks", [])
        period = observation.get("period", "this week")
        summary = f"Weekly Report ({period}): {len(completed)} tasks completed"
        return {"summary": summary, "task_count": len(completed)}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            evidence=[decision["summary"]],
            run_id=ctx.run_id,
        )
''',
            },
        ],
        "readme_extra": (
            "Office automation project.\n\n"
            "Agents:\n"
            "- **TaskMonitorAgent**: Tracks tasks and alerts on overdue items\n"
            "- **ReportGeneratorAgent**: Generates weekly status reports\n"
        ),
    },
}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    # The global --project flag acts as the tenant root directory override.
    # When unset (cwd), we use the default ~/.forge-agent root.
    root_dir = args.project if args.project != Path.cwd() else None
    tenant = LocalTenant(args.tenant, root_dir=root_dir)

    if tenant.project_exists(args.name):
        print(f"Error: project {args.name!r} already exists in tenant {args.tenant!r}.")
        return 1

    target = tenant.create_project(args.name)
    template = TEMPLATES[args.template]

    if args.template == "config-driven":
        return _create_config_driven_project(args, target, template)

    return _create_code_first_project(args, target, template)


def _create_config_driven_project(
    args: argparse.Namespace, target: Path, template: dict[str, Any]
) -> int:
    """Create a low-code/no-code project scaffold."""
    name = args.name
    extra_deps = template["extra_deps"]

    # Directory structure is created by the tenant; ensure optional dirs/files.
    (target / "tests").mkdir(exist_ok=True)
    (target / "generated_agents").mkdir(exist_ok=True)
    (target / "generated_agents" / ".gitkeep").touch(exist_ok=True)

    # pyproject.toml
    deps_lines = ['    "forge-agent",']
    for dep in extra_deps:
        deps_lines.append(f'    "{dep}",')
    deps_str = "\n".join(deps_lines)

    (target / "pyproject.toml").write_text(
        f"""[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
{deps_str}
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["tools*"]
exclude = ["tests*", "pipelines*", "generated_agents*", "agents*", "configs*"]
""",
        encoding="utf-8",
    )

    # Config files
    (target / "configs" / "project.yaml").write_text(
        f"""project:
  name: {name}
  version: 0.1.0
  default_pipeline: example
""",
        encoding="utf-8",
    )

    # Example agent YAML
    (target / "agents" / "example.yaml").write_text(
        """agents:
  - agent_id: example.analyzer
    name: Example Analyzer
    domain: generic
    template: prompt_agent
    config:
      mock_mode: true
      mock_response: |
        {"verdict": "positive", "confidence": 0.85, "evidence": ["Sample evidence"]}
      variables:
        data: data
      prompt: |
        Analyze the following data and provide a structured assessment.

        Data: {data}

        Respond with a JSON object containing:
        - verdict: one of [positive, neutral, negative]
        - confidence: a number between 0 and 1
        - evidence: a list of short strings explaining your reasoning
      output_schema:
        type: object
        properties:
          verdict:
            type: string
            enum: [positive, neutral, negative]
          confidence:
            type: number
            minimum: 0
            maximum: 1
          evidence:
            type: array
            items:
              type: string
        required: [verdict, confidence, evidence]
      output_mapping:
        verdict: verdict
        confidence: confidence
        evidence: evidence
""",
        encoding="utf-8",
    )

    # Example pipeline YAML
    (target / "pipelines" / "example.yaml").write_text(
        """pipeline_id: example
name: Example Pipeline
description: A simple example pipeline that runs a single analyzer agent.
team:
  team_id: example_team
  name: Example Team
  domain: generic
  agent_ids:
    - example.analyzer
  chief_id: generic.chief
  mode: parallel
""",
        encoding="utf-8",
    )

    # Tools package placeholder
    (target / "tools" / "__init__.py").write_text(
        '"""Project-specific tools and MCP tool registrations."""\n',
        encoding="utf-8",
    )

    # Generic runner
    (target / "run.py").write_text(
        f"""\"\"\"Generic runner for {name}.

Interactively create agents/pipelines, or run a pipeline directly.
\"\"\"
from __future__ import annotations

from forge_agent.project.launcher import main

if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )

    # Install scripts
    _write_install_sh(target, name)
    _write_install_bat(target, name)

    # README
    readme_extra = template.get("readme_extra", "")
    (target / "README.md").write_text(
        f"# {name}\n\n"
        f"Created with `forge-agent new {name} --template=config-driven`.\n\n"
        f"**Tenant**: {args.tenant}\n\n"
        f"**Template**: config-driven — {template['description']}\n\n"
        f"{readme_extra}\n\n"
        f"## Project Layout\n\n"
        f"```text\n"
        f"{name}/\n"
        f"├── agents/          # Agent YAML definitions\n"
        f"├── pipelines/       # Pipeline YAML definitions\n"
        f"├── tools/           # Custom MCP tools (optional)\n"
        f"├── configs/         # Project configuration\n"
        f"├── run.py           # Generic pipeline runner\n"
        f"└── pyproject.toml\n"
        f"```\n\n"
        f"## Installation\n\n"
        f"### macOS / Linux\n\n"
        f"```bash\n"
        f"bash install.sh\n"
        f"```\n\n"
        f"### Windows\n\n"
        f"```cmd\n"
        f"install.bat\n"
        f"```\n\n"
        f"## Getting Started\n\n"
        f"```bash\n"
        f"source .venv/bin/activate        # macOS/Linux\n"
        f"# .venv\\Scripts\\activate         # Windows\n"
        f"python run.py --pipeline example\n"
        f"```\n",
        encoding="utf-8",
    )

    print(f"✓ Created {target}/")
    print(f"  Tenant:   {args.tenant}")
    print(f"  Project:  {args.name}")
    print(f"  Template: config-driven ({template['description']})")
    print(f"  Deps:     {', '.join(extra_deps)}")
    print("\nNext steps:")
    print(f"  cd {target}")
    print("  bash install.sh          # macOS/Linux")
    print("  install.bat              # Windows")
    print("  source .venv/bin/activate")
    print("  python run.py --pipeline example")
    print("  # Edit agents/*.yaml and pipelines/*.yaml to customize")
    return 0


def _create_code_first_project(
    args: argparse.Namespace, target: Path, template: dict[str, Any]
) -> int:
    """Create a traditional code-first project scaffold."""
    name = args.name
    template_name = args.template
    extra_deps = template["extra_deps"]
    agents = template["agents"]

    # Directory structure is created by the tenant; ensure optional dirs/files.
    (target / "agents" / "__init__.py").touch(exist_ok=True)
    (target / "tests").mkdir(exist_ok=True)
    (target / "generated_agents").mkdir(exist_ok=True)
    (target / "generated_agents" / ".gitkeep").touch(exist_ok=True)

    # pyproject.toml
    deps_lines = ['    "forge-agent",']
    for dep in extra_deps:
        deps_lines.append(f'    "{dep}",')
    deps_str = "\n".join(deps_lines)

    (target / "pyproject.toml").write_text(
        f"""[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
{deps_str}
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["agents*"]
exclude = ["tests*", "pipelines*", "generated_agents*"]
""",
        encoding="utf-8",
    )

    # Agent files
    (target / "agents" / "__init__.py").touch()
    for agent_def in agents:
        (target / "agents" / agent_def["filename"]).write_text(
            agent_def["code"],
            encoding="utf-8",
        )

    # Install scripts
    _write_install_sh(target, name)
    _write_install_bat(target, name)

    # README
    readme_extra = template.get("readme_extra", "")
    (target / "README.md").write_text(
        f"# {name}\n\n"
        f"Created with `forge-agent new {name} --template={template_name}`.\n\n"
        f"**Tenant**: {args.tenant}\n\n"
        f"**Template**: {template_name} — {template['description']}\n\n"
        f"{readme_extra}\n\n"
        f"## Installation\n\n"
        f"### macOS / Linux\n\n"
        f"```bash\n"
        f"bash install.sh\n"
        f"```\n\n"
        f"### Windows\n\n"
        f"```cmd\n"
        f"install.bat\n"
        f"```\n\n"
        f"## Getting Started\n\n"
        f"```bash\n"
        f"source .venv/bin/activate        # macOS/Linux\n"
        f"# .venv\\Scripts\\activate         # Windows\n"
        f"forge-agent doctor        # check environment\n"
        f"forge-agent llm list      # check LLM providers\n"
        f'forge-agent generate "..."  # generate a new agent\n'
        f"```\n",
        encoding="utf-8",
    )

    # Print summary
    agent_names = [a["class_name"] for a in agents]
    print(f"✓ Created {target}/")
    print(f"  Tenant:   {args.tenant}")
    print(f"  Project:  {args.name}")
    print(f"  Template: {template_name} ({template['description']})")
    print(f"  Agents:   {', '.join(agent_names)}")
    if extra_deps:
        print(f"  Deps:     {', '.join(extra_deps)}")
    print("\nNext steps:")
    print(f"  cd {target}")
    print("  bash install.sh          # macOS/Linux")
    print("  install.bat              # Windows")
    print("  forge-agent doctor")
    print('  forge-agent generate "..."')
    return 0


def _write_install_sh(target: Path, project_name: str) -> None:
    """Write install.sh for macOS/Linux into the generated project."""
    script = f"""#!/usr/bin/env bash
set -euo pipefail

echo "=== {project_name} installer ==="

# --- Detect Python 3.10+ ---
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{{sys.version_info.major}}.{{sys.version_info.minor}}')" 2>/dev/null || true)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] 2>/dev/null && [ "$minor" -ge 10 ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Python 3.10+ not found."
    if command -v brew &>/dev/null; then
        echo "Installing Python 3.12 via Homebrew..."
        brew install python@3.12
        PYTHON="python3.12"
    elif command -v apt-get &>/dev/null; then
        echo "Installing Python 3.12 via apt..."
        sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv
        PYTHON="python3.12"
    else
        echo "Please install Python 3.10+ first: https://www.python.org/downloads/"
        exit 1
    fi
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"

# --- Create venv & install ---
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

source .venv/bin/activate
echo "Installing dependencies..."
pip install -e ".[all]" 2>/dev/null || pip install -e .

echo ""
echo "Done! Activate with:  source .venv/bin/activate"
"""
    (target / "install.sh").write_text(script, encoding="utf-8")
    (target / "install.sh").chmod(0o755)


def _write_install_bat(target: Path, project_name: str) -> None:
    """Write install.bat for Windows into the generated project."""
    script = f"""@echo off
echo === {project_name} installer ===

set PYTHON=

for %%P in (python3.12 python3.11 python3.10 python) do (
    where %%P >nul 2>&1
    if not errorlevel 1 (
        %%P -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
        if not errorlevel 1 (
            set PYTHON=%%P
            goto :found
        )
    )
)

echo Python 3.10+ not found.
echo Please install from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
exit /b 1

:found
echo Using Python: %PYTHON%
%PYTHON% --version

if not exist ".venv" (
    echo Creating virtual environment...
    %PYTHON% -m venv .venv
)

call .venv\\Scripts\\activate.bat
echo Installing dependencies...
pip install -e ".[all]" 2>nul || pip install -e .

echo.
echo Done! Activate with:  .venv\\Scripts\\activate.bat
"""
    (target / "install.bat").write_text(script, encoding="utf-8")
