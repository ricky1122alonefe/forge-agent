#!/usr/bin/env bash
# P0.6 golden path smoke check against a running forge-agent server.
# Usage: ./scripts/golden_path_check.sh [base_url]
# Example: ./scripts/golden_path_check.sh http://127.0.0.1:8787/t/default/p/default

set -euo pipefail

BASE="${1:-http://127.0.0.1:8787/t/default/p/default}"
API="$BASE/api"

echo "==> P0.6 golden path check @ $BASE"

curl -sf "$API/../api/health" >/dev/null || curl -sf "http://127.0.0.1:8787/api/health" >/dev/null
echo "  health OK"

curl -sf -X POST "$API/agents/from-preset" \
  -H 'Content-Type: application/json' \
  -d '{"preset_id":"weibo_trend","agent_id":"weibo_analyst"}' >/dev/null
curl -sf -X POST "$API/agents/from-preset" \
  -H 'Content-Type: application/json' \
  -d '{"preset_id":"xhs_trend","agent_id":"xhs_analyst"}' >/dev/null
echo "  agents OK"

curl -sf -X POST "$API/pipelines" \
  -H 'Content-Type: application/json' \
  -d '{"pipeline_id":"trend","name":"Trend","agent_ids":["weibo_analyst","xhs_analyst"],"chief_id":"generic.chief","mode":"parallel"}' >/dev/null
echo "  pipeline OK"

RUN=$(curl -sf -X POST "$API/pipelines/trend/run" \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"keyword":"labubu"}}')
echo "$RUN" | grep -q '"success": true'
echo "  run OK"

echo "==> P0.6 passed"
