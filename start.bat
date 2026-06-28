@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo   ╔══════════════════════════════════════════════╗
echo   ║     预知梦基金 (Prophetic Dream Fund)         ║
echo   ║     v1.0  —  个人投资者基金投研平台            ║
echo   ╚══════════════════════════════════════════════╝
echo.

:: --------------------------------------------------------------------
:: Step 1: Check prerequisites
:: --------------------------------------------------------------------
echo [检查] 环境依赖...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请安装 Python 3.11+
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请安装 Node.js 18+
    echo         下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo         Python: 已安装
echo         Node.js: 已安装

:: --------------------------------------------------------------------
:: Step 2: Backend setup (first run only)
:: --------------------------------------------------------------------
if not exist "backend\fund_app.db" (
    echo.
    echo [初始化] 首次运行 — 安装后端依赖...
    cd backend
    pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [错误] 后端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    echo [初始化] 创建数据库...
    python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
    if %errorlevel% neq 0 (
        echo [错误] 数据库初始化失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo         ✓ 后端初始化完成
)

:: --------------------------------------------------------------------
:: Step 3: Frontend setup (first run only)
:: --------------------------------------------------------------------
if not exist "frontend\node_modules" (
    echo.
    echo [初始化] 首次运行 — 安装前端依赖 (可能需要 1-2 分钟)...
    cd frontend
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo         ✓ 前端初始化完成
)

:: --------------------------------------------------------------------
:: Step 4: Launch backend
:: --------------------------------------------------------------------
echo.
echo [启动] 后端服务 (http://127.0.0.1:8000)...
start "预知梦基金-后端" cmd /c "cd /d %~dp0backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: Wait for backend to be ready
echo        等待后端就绪...
timeout /t 3 /nobreak >nul

:: --------------------------------------------------------------------
:: Step 5: Launch frontend
:: --------------------------------------------------------------------
echo [启动] 前端服务 (http://127.0.0.1:5173)...
echo.
echo   ┌─────────────────────────────────────────────┐
echo   │  浏览器打开 http://localhost:5173 即可使用   │
echo   │  按 Ctrl+C 停止所有服务                      │
echo   └─────────────────────────────────────────────┘
echo.

cd frontend
call npx vite --host 127.0.0.1 --port 5173

:: When Vite exits (Ctrl+C), also kill the backend
taskkill /fi "WINDOWTITLE eq 预知梦基金-后端*" /f >nul 2>nul
echo.
echo [退出] 预知梦基金已停止
pause
