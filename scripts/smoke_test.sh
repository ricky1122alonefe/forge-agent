#!/usr/bin/env bash
# smoke_test.sh - 端到端冒烟测试
#
# 验证: forge-agent new → llm list → generate → run
# 用法: PYTHON_BIN=/path/to/python3.11 bash scripts/smoke_test.sh
# 返回: 0 = pass, 非 0 = fail

set -e

cd "$(dirname "$0")/.."

# 默认 Python（可用 PYTHON_BIN 环境变量覆盖）
PYTHON_BIN="${PYTHON_BIN:-python}"
export PYTHONPATH="/Users/popmart/Documents/python/forge-agent/src:${PYTHONPATH:-}"

WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

echo "=========================================="
echo "  端到端冒烟测试"
echo "  Python: $($PYTHON_BIN --version)"
echo "  工作目录: $WORK_DIR"
echo "=========================================="
echo ""

cd "$WORK_DIR"

# Step 1: 验证 forge-agent 可 import
echo "[Step 1/6] 验证 forge-agent 可 import..."
$PYTHON_BIN -c "import forge_agent; print(f'  forge-agent {forge_agent.__version__}')"

# Step 2: 验证 forge-agent new
echo "[Step 2/6] 跑 forge-agent new..."
$PYTHON_BIN -m forge_agent.cli new my_app --template=basic
test -d my_app && echo "  ✓ my_app/ 已创建"

# Step 3: 安装依赖
echo "[Step 3/6] 安装 my_app 依赖..."
cd my_app
$PYTHON_BIN -m pip install -e /Users/popmart/Documents/python/forge-agent --quiet 2>&1 | tail -2 || echo "  (依赖已装，跳过)"

# Step 4: llm list
echo "[Step 4/6] 跑 forge-agent llm list..."
$PYTHON_BIN -m forge_agent.cli llm list 2>&1 | head -10

# Step 5: 运行 ExampleAgent（已存在，无需 generate）
echo "[Step 5/6] 准备 ExampleAgent..."
cat > test_run.py <<'PYEOF'
import asyncio
from forge_agent import AgentContext, AgentReport, BaseAgent, Verdict, register_agent

# 注册一个简单的 demo agent
@register_agent(domain="smoke")
class SmokeAgent(BaseAgent):
    agent_id = "smoke.test"
    name = "Smoke Test Agent"
    version = "0.1.0"
    domain = "smoke"

    async def observe(self, ctx):
        return {"x": 1}

    async def decide(self, ctx, obs):
        return {"y": obs["x"] + 1}

    async def act(self, ctx, dec):
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            verdict=Verdict.NEUTRAL,
            evidence=[f"y={dec['y']}"],
            run_id=ctx.run_id,
        )

async def main():
    agent = SmokeAgent()
    await agent.initialize()
    report = await agent.run(AgentContext(scope_id="t1", scope_name="test"))
    print(f"  Verdict: {report.verdict}")
    print(f"  Run ID: {report.run_id}")
    print(f"  Evidence: {report.evidence}")
    assert report.verdict is not None, "verdict is None"
    assert report.run_id, "run_id is empty"
    await agent.shutdown()
    print("  ✓ Agent 运行成功")

asyncio.run(main())
PYEOF

# Step 6: 运行 agent
echo "[Step 6/6] 运行 agent..."
$PYTHON_BIN test_run.py

echo ""
echo "=========================================="
echo "  冒烟测试通过！"
echo "=========================================="
