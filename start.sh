#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     预知梦基金 (Prophetic Dream Fund)         ║"
echo "  ║     v1.0  —  个人投资者基金投研平台            ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# --- Check prerequisites ---
echo "[检查] 环境依赖..."

if ! command -v python3 &>/dev/null; then
    echo "[错误] 未找到 Python3，请安装 Python 3.11+"
    exit 1
fi

if ! command -v node &>/dev/null; then
    echo "[错误] 未找到 Node.js，请安装 Node.js 18+"
    exit 1
fi

echo "        Python: $(python3 --version)"
echo "        Node.js: $(node --version)"

# --- Backend first-run setup ---
if [ ! -f "backend/fund_app.db" ]; then
    echo ""
    echo "[初始化] 首次运行 — 安装后端依赖..."
    cd backend
    pip install -r requirements.txt -q
    echo "[初始化] 创建数据库..."
    python3 -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
    cd ..
    echo "        ✓ 后端初始化完成"
fi

# --- Frontend first-run setup ---
if [ ! -d "frontend/node_modules" ]; then
    echo ""
    echo "[初始化] 首次运行 — 安装前端依赖..."
    cd frontend
    npm install
    cd ..
    echo "        ✓ 前端初始化完成"
fi

# --- Launch backend in background ---
echo ""
echo "[启动] 后端服务 (http://127.0.0.1:8000)..."
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend
sleep 2

# --- Launch frontend ---
echo "[启动] 前端服务 (http://127.0.0.1:5173)..."
echo ""
echo "  ┌─────────────────────────────────────────────┐"
echo "  │  浏览器打开 http://localhost:5173 即可使用   │"
echo "  │  按 Ctrl+C 停止所有服务                      │"
echo "  └─────────────────────────────────────────────┘"
echo ""

# Trap to clean up backend on exit
cleanup() {
    echo ""
    echo "[退出] 正在停止服务..."
    kill "$BACKEND_PID" 2>/dev/null || true
    echo "[退出] 预知梦基金已停止"
}
trap cleanup EXIT INT TERM

cd frontend
npx vite --host 127.0.0.1 --port 5173
