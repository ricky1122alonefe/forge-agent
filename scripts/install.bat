@echo off
setlocal enabledelayedexpansion

:: forge-agent 一键安装脚本 (Windows)
:: 用法: scripts\install.bat

echo.
echo ╔══════════════════════════════════════════════╗
echo ║      forge-agent 安装程序 v0.3.0            ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ── 1. 检测 Python ──────────────────────────────────
set "PYTHON_CMD="

:: 尝试常见的 Python 命令
for %%P in (python3.14 python3.13 python3.12 python3.11 python3.10 python py) do (
    if not defined PYTHON_CMD (
        %%P --version >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=2 delims= " %%V in ('%%P --version 2^>^&1') do set "PY_VER=%%V"
            for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
                set "PY_MAJOR=%%A"
                set "PY_MINOR=%%B"
            )
            if !PY_MAJOR! geq 3 (
                if !PY_MINOR! geq 10 (
                    set "PYTHON_CMD=%%P"
                    echo [ OK ]  找到 Python: !PY_VER! ^(%%P^)
                )
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo [ ERR ] 未找到 Python 3.10+
    echo.
    echo 请安装 Python 3.10 或更高版本:
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: ── 2. 确定项目目录 ──────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

:: 检查是否是本地源码
set "IS_LOCAL=false"
if exist "%PROJECT_DIR%\pyproject.toml" (
    findstr /C:"forge-agent" "%PROJECT_DIR%\pyproject.toml" >nul 2>&1
    if !errorlevel! equ 0 (
        set "IS_LOCAL=true"
        echo [INFO]  检测到本地源码: %PROJECT_DIR%
    )
)

:: ── 3. 创建虚拟环境 ──────────────────────────────────
set "VENV_DIR=%PROJECT_DIR%\.venv"

if exist "%VENV_DIR%" (
    echo [WARN]  虚拟环境已存在: %VENV_DIR%\
    echo [INFO]  跳过创建，直接安装依赖...
) else (
    echo [INFO]  创建虚拟环境: %VENV_DIR%\
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo [ ERR ] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [ OK ]  虚拟环境创建成功
)

:: 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"
echo [ OK ]  已激活虚拟环境

:: ── 4. 升级 pip ──────────────────────────────────────
echo [INFO]  升级 pip ...
python -m pip install --upgrade pip setuptools wheel -q
echo [ OK ]  pip 已升级

:: ── 5. 安装 forge-agent ──────────────────────────────
if "%IS_LOCAL%"=="true" (
    echo [INFO]  从本地源码安装 forge-agent ^(开发模式^) ...
    cd /d "%PROJECT_DIR%"
    pip install -e ".[all]" -q
) else (
    echo [INFO]  从 PyPI 安装 forge-agent ...
    pip install "forge-agent[all]" -q
    if !errorlevel! neq 0 (
        echo [WARN]  PyPI 安装失败，尝试从 GitHub 安装 ...
        pip install "git+https://github.com/ricky1122alonefe/forge-agent.git#egg=forge-agent[all]" -q
    )
)
echo [ OK ]  forge-agent 安装成功

:: ── 6. 验证安装 ──────────────────────────────────────
echo.
echo [INFO]  验证安装 ...

forge-agent doctor >nul 2>&1
if !errorlevel! equ 0 (
    echo [ OK ]  环境检查通过
) else (
    echo [WARN]  环境检查有警告，运行 'forge-agent doctor' 查看详情
)

:: ── 7. 完成 ──────────────────────────────────────────
echo.
echo ╔══════════════════════════════════════════════╗
echo ║            安装完成!                         ║
echo ╚══════════════════════════════════════════════╝
echo.
echo   1. 创建项目:
echo      forge-agent new my-project --template basic
echo      cd my-project
echo.
echo   2. 安装项目依赖:
echo      pip install -e .
echo.
echo   3. 生成 Agent:
echo      forge-agent generate "你的需求描述"
echo.
echo   4. 启动 Dashboard:
echo      forge-agent dashboard
echo.
echo   查看帮助:  forge-agent --help
echo   文档:      https://forge-agent.readthedocs.io/
echo.
echo 提示: 每次打开新终端需要先激活虚拟环境:
echo   %VENV_DIR%\Scripts\activate.bat
echo.

pause
