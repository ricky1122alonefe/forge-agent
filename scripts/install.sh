#!/usr/bin/env bash
# forge-agent 一键安装脚本
# 用法: bash scripts/install.sh
#   或: curl -fsSL https://raw.githubusercontent.com/ricky1122alonefe/forge-agent/main/scripts/install.sh | bash

set -euo pipefail

# ── 颜色 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ ERR ]${NC} $*"; }

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INSTALL_EXTRAS="${1:-all}"  # 默认安装 all extras

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║      forge-agent 安装程序 v0.3.0            ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. 检测操作系统 ──────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
info "系统: ${OS} ${ARCH}"

# ── 2. 检测 / 安装 Python 3.10+ ──────────────────────
find_python() {
    local candidates=("python3.14" "python3.13" "python3.12" "python3.11" "python3.10" "python3")
    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
            if [[ -n "$ver" ]]; then
                local major minor
                major=$(echo "$ver" | cut -d. -f1)
                minor=$(echo "$ver" | cut -d. -f2)
                if (( major > MIN_PYTHON_MAJOR || (major == MIN_PYTHON_MAJOR && minor >= MIN_PYTHON_MINOR) )); then
                    echo "$cmd"
                    return 0
                fi
            fi
        fi
    done
    return 1
}

PYTHON_CMD=""
if PYTHON_CMD=$(find_python); then
    PY_VERSION=$($PYTHON_CMD --version 2>&1)
    ok "找到 Python: ${PY_VERSION} (${PYTHON_CMD})"
else
    warn "未找到 Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+"
    echo ""

    if [[ "$OS" == "Darwin" ]]; then
        info "检测到 macOS，尝试通过 Homebrew 安装 Python 3.12 ..."
        if ! command -v brew &>/dev/null; then
            err "未找到 Homebrew，请先安装: https://brew.sh"
            exit 1
        fi
        brew install python@3.12
        PYTHON_CMD="/opt/homebrew/bin/python3.12"
        if [[ ! -x "$PYTHON_CMD" ]]; then
            PYTHON_CMD="$(brew --prefix python@3.12)/bin/python3.12"
        fi
    elif [[ "$OS" == "Linux" ]]; then
        info "检测到 Linux，尝试安装 Python 3.12 ..."
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
            PYTHON_CMD="python3.12"
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3.12 python3.12-devel
            PYTHON_CMD="python3.12"
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python3.12
            PYTHON_CMD="python3.12"
        else
            err "无法自动安装 Python 3.12，请手动安装后重试"
            exit 1
        fi
    else
        err "不支持的操作系统: ${OS}"
        err "请手动安装 Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+: https://www.python.org/downloads/"
        exit 1
    fi

    if [[ -n "$PYTHON_CMD" ]] && $PYTHON_CMD --version &>/dev/null; then
        ok "Python 安装成功: $($PYTHON_CMD --version)"
    else
        err "Python 安装失败，请手动安装"
        exit 1
    fi
fi

# ── 3. 确定项目目录 ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 判断是从项目目录运行还是从远程下载
IS_LOCAL=false
if [[ -f "${PROJECT_DIR}/pyproject.toml" ]] && grep -q "forge-agent" "${PROJECT_DIR}/pyproject.toml" 2>/dev/null; then
    IS_LOCAL=true
    info "检测到本地源码: ${PROJECT_DIR}"
fi

# ── 4. 创建虚拟环境 ──────────────────────────────────
VENV_DIR="${PROJECT_DIR}/.venv"

if [[ -d "$VENV_DIR" ]]; then
    warn "虚拟环境已存在: ${VENV_DIR}/"
    info "跳过创建，直接安装依赖..."
else
    info "创建虚拟环境: ${VENV_DIR}/"
    $PYTHON_CMD -m venv "$VENV_DIR"
    ok "虚拟环境创建成功"
fi

# 激活虚拟环境
source "${VENV_DIR}/bin/activate"
ok "已激活虚拟环境: $(which python)"

# ── 5. 升级 pip ──────────────────────────────────────
info "升级 pip ..."
python -m pip install --upgrade pip setuptools wheel -q
ok "pip 已升级"

# ── 6. 安装 forge-agent ──────────────────────────────
if [[ "$IS_LOCAL" == true ]]; then
    info "从本地源码安装 forge-agent (开发模式) ..."
    cd "$PROJECT_DIR"
    pip install -e ".[${INSTALL_EXTRAS}]" -q
else
    info "从 PyPI 安装 forge-agent ..."
    pip install "forge-agent[${INSTALL_EXTRAS}]" -q 2>/dev/null || {
        warn "PyPI 安装失败，尝试从 GitHub 安装 ..."
        pip install "git+https://github.com/ricky1122alonefe/forge-agent.git#egg=forge-agent[${INSTALL_EXTRAS}]" -q
    }
fi
ok "forge-agent 安装成功"

# ── 7. 创建全局命令链接 ──────────────────────────────
FORGE_BIN="${VENV_DIR}/bin/forge-agent"
LINK_CREATED=false

if [[ -f "$FORGE_BIN" ]]; then
    # 尝试 /usr/local/bin (macOS/Linux 通用)
    if [[ -d "/usr/local/bin" ]] && [[ -w "/usr/local/bin" || "$(id -u)" -eq 0 ]]; then
        ln -sf "$FORGE_BIN" /usr/local/bin/forge-agent 2>/dev/null && LINK_CREATED=true
    fi

    # 尝试 Homebrew 路径 (macOS Apple Silicon)
    if [[ "$LINK_CREATED" == false ]] && [[ -d "/opt/homebrew/bin" ]]; then
        ln -sf "$FORGE_BIN" /opt/homebrew/bin/forge-agent 2>/dev/null && LINK_CREATED=true
    fi

    # 尝试 ~/.local/bin (Linux 用户级)
    if [[ "$LINK_CREATED" == false ]]; then
        mkdir -p "$HOME/.local/bin"
        ln -sf "$FORGE_BIN" "$HOME/.local/bin/forge-agent" 2>/dev/null && LINK_CREATED=true
        # 确保 ~/.local/bin 在 PATH 中
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            SHELL_RC=""
            if [[ -f "$HOME/.zshrc" ]]; then
                SHELL_RC="$HOME/.zshrc"
            elif [[ -f "$HOME/.bashrc" ]]; then
                SHELL_RC="$HOME/.bashrc"
            fi
            if [[ -n "$SHELL_RC" ]]; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
                info "已添加 ~/.local/bin 到 PATH (${SHELL_RC})"
            fi
        fi
    fi
fi

if [[ "$LINK_CREATED" == true ]]; then
    ok "已创建全局命令链接: forge-agent"
else
    warn "无法创建全局链接，你需要先激活虚拟环境才能使用 forge-agent 命令"
    warn "  source ${VENV_DIR}/bin/activate"
fi

# ── 8. 安装 pre-commit hooks (开发模式) ──────────────
if [[ "$IS_LOCAL" == true ]] && [[ -f "${PROJECT_DIR}/.pre-commit-config.yaml" ]]; then
    info "安装 pre-commit hooks ..."
    pip install pre-commit -q
    pre-commit install 2>/dev/null || true
    ok "pre-commit hooks 已安装"
fi

# ── 9. 验证安装 ──────────────────────────────────────
echo ""
info "验证安装 ..."

if forge-agent doctor 2>/dev/null; then
    ok "环境检查通过"
else
    warn "环境检查有警告，运行 'forge-agent doctor' 查看详情"
fi

# ── 10. 完成 ─────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║            安装完成!                         ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}1. 创建项目:${NC}"
echo -e "     forge-agent new my-project --template basic"
echo -e "     cd my-project"
echo ""
echo -e "  ${BOLD}2. 安装项目依赖:${NC}"
echo -e "     pip install -e ."
echo ""
echo -e "  ${BOLD}3. 生成 Agent:${NC}"
echo -e "     forge-agent generate \"你的需求描述\""
echo ""
echo -e "  ${BOLD}4. 启动 Dashboard:${NC}"
echo -e "     forge-agent dashboard"
echo ""
echo -e "  ${BOLD}查看帮助:${NC}  forge-agent --help"
echo -e "  ${BOLD}文档:${NC}      https://forge-agent.readthedocs.io/"
echo ""
