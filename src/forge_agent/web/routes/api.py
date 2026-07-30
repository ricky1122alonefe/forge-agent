"""API routes aggregator (S4.1 split).

All route logic moved to per-domain sub-modules. This file only
assembles sub-routers under the /api prefix.

Sub-modules:
  - agent_types: /agent-types/*
  - agents:      /agents/*, /agent-presets
  - pipelines:   /pipelines/*, /pipeline-presets
  - llm:         /llm/*
  - bundles:     /market/*, /bundles/*, */export
  - architect:   /architect/*
  - spec:        /agent-spec/*
  - runs:        /runs/*, /pipelines/*/runs (S4.2)
"""

from __future__ import annotations

from fastapi import APIRouter

from forge_agent.web.routes import (
    agent_types,
    agents,
    architect,
    bundles,
    llm,
    pipelines,
    runs,
    spec,
)

router = APIRouter(prefix="/api")

router.include_router(agent_types.router)
router.include_router(agents.router)
router.include_router(pipelines.router)
router.include_router(llm.router)
router.include_router(bundles.router)
router.include_router(architect.router)
router.include_router(spec.router)
router.include_router(runs.router)
