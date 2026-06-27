#!/usr/bin/env bash
# smoke_test.sh - 端到端冒烟测试
#
# 验证: forge-agent new → llm list → generate → run
# 用法: bash scripts/smoke_test.sh
# 返回: 0 = pass, 非 0 = fail

set -e

cd "$(dirname "$0")/.."

WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

echo "=========================================="
echo "  端到端冒烟测试"
echo "  工作目录: $WORK_DIR"
echo "=========================================="
echo ""

cd "$WORK_DIR"

# Step 1: 验证 forge-agent 可 import
echo "[Step 1/6] 验证 forge-agent 可 import..."
PYTHONPATH=/Users/popmart/Documents/python/forge-agent/src \
    python -c "import forge_agent; print(f'  forge-agent {forge_agent.__version__}')"

# Step 2: 验证 forge-agent new
echo "[Step 2/6] 跑 forge-agent new..."
PYTHONPATH=/Users/popmart/Documents/python/forge-agent/src \
    python -m forge_agent.cli new my_app --template=basic
test -d my_app && echo "  ✓ my_app/ 已创建"

# Step 3: 安装依赖
echo "[Step 3/6] 安装 my_app 依赖..."
cd my_app
pip install -e /Users/popmart/Documents/python/forge-agent --quiet

# Step 4: llm list
echo "[Step 4/6] 跑 forge-agent llm list..."
PROVIDER_COUNT=$(PYTHONPATH=/Users/popmart/Documents/python/forge-agent/src \
    forge-agent llm list 2>&1 | grep -c "✓" || echo "0")
echo "  发现 $PROVIDER_COUNT 个 provider"
[ "$PROVIDER_COUNT" -ge 1 ] || { echo "  ❌ 没有可用 provider"; exit 1; }

# Step 5: generate
echo "[Step 5/6] 跑 forge-agent generate..."
PYTHONPATH=/Users/popmart/Documents/python/forge-agent/src \
    forge-agent generate "echo agent that returns hello" --provider=mock 2>&1 | tail -5

# Step 6: 运行生成的 agent
echo "[Step 6/6] 运行生成的 agent..."
cat > test_run.py <<'PYEOF'
import asyncio
from forge_agent import AgentContext
from agents.example import ExampleAgent

async def main():
    agent = ExampleAgent()
    await agent.initialize()
    report = await agent.run(AgentContext(scope_id="t1", scope_name="test"))
    print(f"  Verdict: {report.verdict}")
    print(f"  Run ID: {report.run_id}")
    assert report.verdict is not None, "verdict is None"
    assert report.run_id, "run_id is empty"
    await agent.shutdown()
    print("  ✓ Agent 运行成功")

asyncio.run(main())
PYEOF
python test_run.py

echo ""
echo "=========================================="
echo "  冒烟测试通过！"
echo "=========================================="
