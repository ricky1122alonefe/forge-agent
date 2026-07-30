"""Task run management routes (S4.2).

Exposes the runtime layer (TaskRunner) via REST:
- POST /pipelines/{pipeline_id}/runs — async submit (returns run_id immediately)
- GET /runs — list runs
- GET /runs/{run_id} — get run status
- POST /runs/{run_id}/cancel — cancel a run

The TaskRunner instance is stored in app.state.runner and initialised
at startup. If no runner is configured, endpoints return 503.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


def _get_runner(request: Request):
    runner = getattr(request.app.state, "runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Task runner not initialised")
    return runner


class SubmitRunPayload(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    callback_url: str | None = None


@router.post("/pipelines/{pipeline_id}/runs")
async def submit_run(
    pipeline_id: str,
    body: SubmitRunPayload,
    request: Request,
) -> dict[str, Any]:
    """Submit a pipeline for async execution. Returns immediately with run_id."""
    runner = _get_runner(request)
    run = await runner.submit(
        pipeline_id,
        payload=body.payload,
        callback_url=body.callback_url,
    )
    return {"success": True, "run_id": run.run_id, "status": run.status}


@router.get("/runs")
async def list_runs(
    request: Request,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List task runs with optional status filter."""
    runner = _get_runner(request)
    runs = runner.store.list(status=status, limit=limit)
    return {"runs": [r.to_dict() for r in runs], "count": len(runs)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    """Get the status and result of a specific run."""
    runner = _get_runner(request)
    run = runner.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    return run.to_dict()


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> dict[str, Any]:
    """Cancel a pending or running task."""
    runner = _get_runner(request)
    cancelled = await runner.cancel(run_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id!r} cannot be cancelled (not found or already terminal)",
        )
    return {"success": True, "run_id": run_id}
