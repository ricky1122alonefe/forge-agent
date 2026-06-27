#!/usr/bin/env bash
# check_dashboard.sh — Dashboard MVP 自动化检查
#
# 用法: bash scripts/check_dashboard.sh
# 返回: 0 = 全部通过, 1 = 有失败

set -e

cd "$(dirname "$0")/.."

PASS=0
FAIL=0
TOTAL=0

check() {
    local id="$1"
    local desc="$2"
    TOTAL=$((TOTAL + 1))

    if eval "$3" > /dev/null 2>&1; then
        echo "[$id] $desc ✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "[$id] $desc ❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
}

echo "=========================================="
echo "  Dashboard MVP 自动化检查"
echo "=========================================="
echo ""

# D1.1: FastAPI skeleton
check "D1.1" "FastAPI app 骨架" \
    "[ -f src/forge_agent/dashboard/app.py ] && python -c 'from forge_agent.dashboard.app import create_app'"

# D1.2: Agent list page
check "D1.2" "页面 1：Agent 列表" \
    "[ -f src/forge_agent/dashboard/templates/index.html ] && [ -f src/forge_agent/dashboard/templates/base.html ]"

# D1.3: REST API
check "D1.3" "REST API 读 MANIFEST.json" \
    "[ -f src/forge_agent/dashboard/data/manifest.py ] && python -c 'from forge_agent.dashboard.data.manifest import load_manifest'"

# D1.4: HTMX + Tailwind
check "D1.4" "Tailwind + HTMX 美化" \
    "[ -f src/forge_agent/dashboard/static/forge.css ] && grep -q 'htmx' src/forge_agent/dashboard/templates/base.html"

# D1.5: CLI
check "D1.5" "forge-agent dashboard CLI" \
    "[ -f src/forge_agent/cli/cmd_dashboard.py ] && python -m forge_agent.cli dashboard --help"

# Optional: actual tests
check "tests" "Dashboard 单元测试" \
    "pytest tests/unit/dashboard/ -q"

echo ""
echo "=========================================="
echo "  结果: $PASS/$TOTAL passed"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo "🎉 Dashboard MVP 全部通过！"
    exit 0
else
    echo "⚠️  有 $FAIL 项未完成，请查看 docs/tasks/dashboard-overview.md"
    exit 1
fi
