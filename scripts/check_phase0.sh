#!/usr/bin/env bash
# check_phase0.sh - Phase 0 自动化检查脚本
#
# 用法: bash scripts/check_phase0.sh
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
echo "  Phase 0 自动化检查"
echo "=========================================="
echo ""

# T0.1: Python 3.10+
check "T0.1" "Python 3.10+ 真环境" \
    "python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'"

# T0.2: LICENSE
check "T0.2" "LICENSE 文件" \
    "[ -f LICENSE ] && grep -q 'MIT License' LICENSE"

# T0.3: CHANGELOG.md
check "T0.3" "CHANGELOG.md" \
    "[ -f CHANGELOG.md ] && grep -q '0.3.0' CHANGELOG.md"

# T0.4: CI
check "T0.4" "GitHub Actions CI" \
    "[ -f .github/workflows/test.yml ]"

# T0.5: pre-commit
check "T0.5" "pre-commit 配置" \
    "[ -f .pre-commit-config.yaml ] && [ -f .editorconfig ]"

# T0.6: 冒烟测试
check "T0.6" "端到端冒烟测试" \
    "[ -f scripts/smoke_test.sh ] && [ -x scripts/smoke_test.sh ]"

echo ""
echo "=========================================="
echo "  结果: $PASS/$TOTAL passed"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo "🎉 Phase 0 全部通过！可以进入 Phase 1"
    exit 0
else
    echo "⚠️  有 $FAIL 项未完成，请查看 docs/tasks/phase-0-overview.md"
    exit 1
fi
