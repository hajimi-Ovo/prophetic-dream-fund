# 预知梦基金 — 轻量化重构 Phase 1 详细设计

> **版本**: v1.0
> **日期**: 2026-06-28
> **范围**: Phase 1 — 去 Docker 化 + SQLite 替代 PostgreSQL/Redis + 一键启动

---

## 目录

1. [变更总览](#1-变更总览)
2. [删除文件清单](#2-删除文件清单)
3. [新增文件详细设计](#3-新增文件详细设计)
4. [修改文件详细设计](#4-修改文件详细设计)
5. [数据流变化](#5-数据流变化)
6. [启动流程](#6-启动流程)
7. [兼容性与风险](#7-兼容性与风险)

---

## 1. 变更总览

### 1.1 变更文件一览

| 操作 | 文件 | 说明 |
|------|------|------|
| **删** | `docker-compose.yml` | Docker 编排配置 |
| **删** | `nginx.conf` | 顶层 Nginx 反向代理配置 |
| **删** | `backend/Dockerfile` | 后端容器镜像 |
| **删** | `backend/.dockerignore` | Docker 构建忽略 |
| **删** | `frontend/Dockerfile` | 前端容器镜像 |
| **删** | `frontend/.dockerignore` | Docker 构建忽略 |
| **删** | `frontend/nginx.conf` | 前端 Nginx 静态文件服务配置 |
| **删** | `backend/app/redis_client.py` | Redis 客户端 (整个文件) |
| **改** | `backend/app/config.py` | 移除 REDIS_URL，DATABASE_URL 默认值改为 SQLite |
| **改** | `backend/app/database.py` | 移除 PostgreSQL 连接池参数，SQLite 适配 |
| **改** | `backend/app/main.py` | lifespan 中移除 Redis/Scheduler 初始化 |
| **改** | `backend/app/api/dependencies.py` | 移除 `get_redis` 导出 |
| **改** | `backend/app/services/cache_service.py` | Redis → 内存字典 + TTL |
| **改** | `backend/app/services/fund_service.py` | 构造函数移除 Redis 参数 |
| **改** | `backend/app/services/holding_service.py` | 构造函数移除 Redis 参数 |
| **改** | `backend/app/services/dashboard_service.py` | 构造函数移除 Redis 参数 |
| **改** | `backend/app/api/funds.py` | 移除 Redis 依赖注入 |
| **改** | `backend/app/api/holdings.py` | 移除 Redis 依赖注入 |
| **改** | `backend/app/api/dashboard.py` | 移除 Redis 依赖注入 |
| **改** | `backend/app/api/watchlist.py` | 移除 Redis 依赖注入 |
| **改** | `backend/app/api/ocr.py` | 移除 Redis 依赖注入 |
| **改** | `backend/app/api/data_mgmt.py` | 移除 Redis 依赖注入，使用内存缓存 |
| **改** | `backend/app/scheduler/jobs.py` | Redis 操作改为内存缓存 |
| **改** | `backend/requirements.txt` | 移除 redis, asyncpg；新增 aiosqlite |
| **改** | `backend/.env` | 简化为最小配置 |
| **改** | `README.md` | 全面重写 |
| **新** | `start.bat` | Windows 一键启动脚本 |
| **新** | `start.sh` | Linux/macOS 一键启动脚本 |

### 1.2 不变的组件

| 组件 | 原因 |
|------|------|
| 前端 (React + Vite) | Vite dev server 启动 < 1s，不是瓶颈 |
| FastAPI 框架 | 本身轻量，`uvicorn` 启动 < 1s |
| SQLAlchemy ORM | 保持 async 用法，只换驱动 |
| APScheduler | Phase 1 保留，仅修改内部 Redis 调用为内存缓存 |
| 所有 API 路由 | 接口签名不变 (移除 Redis 参数后对外透明) |
| 所有 Pydantic Schema | 无变更 |
| 所有 Engine 模块 | fund_ranker / risk_scorer / timing_advisor / portfolio_builder / backtester 均不涉及 Redis |
| 测试文件 | Phase 1 暂不改动，Phase 2 整体适配 |

---

## 2. 删除文件清单

### 2.1 Docker 相关 (7 个文件)

```
rm docker-compose.yml
rm nginx.conf
rm backend/Dockerfile
rm backend/.dockerignore
rm frontend/Dockerfile
rm frontend/.dockerignore
rm frontend/nginx.conf
```

### 2.2 Redis 客户端

```
rm backend/app/redis_client.py
```

**理由**: Redis 是唯一的外部缓存依赖。移除后，缓存功能由新的内存缓存 (`backend/app/cache.py`) 接管，对外接口保持兼容。

---

## 3. 新增文件详细设计

### 3.1 `backend/app/cache.py` — 内存 TTL 缓存

**设计目标**: 完全替代 `redis_client.py` + `cache_service.py` 中的 Redis 操作，提供一个**接口兼容**的内存缓存层。

**接口设计**:

```python
"""
In-memory TTL cache — drop-in replacement for Redis-backed cache.

Provides the same CacheService public API backed by a dict + asyncio.Lock.
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON encoder (unchanged from original CacheService)
# ---------------------------------------------------------------------------
class _CacheEncoder(json.JSONEncoder):
    def default(self, obj: object) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, date | datetime):
            return obj.isoformat()
        return super().default(obj)


def _serialize(value: Any) -> str:
    return json.dumps(value, cls=_CacheEncoder, ensure_ascii=False)


def _deserialize(text: str | bytes | None) -> Any:
    if text is None:
        return None
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to decode cache JSON: %.100s...", text)
        return None


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
class _CacheEntry:
    """A single cache entry with value and optional expiry."""
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: int | None = None) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl if ttl else None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and time.monotonic() > self.expires_at


class CacheService:
    """
    Async in-memory cache with per-key TTL support.

    Thread-safe via asyncio.Lock. Drop-in replacement for the Redis-backed
    CacheService — same public method names and signatures.
    """

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Latest NAV
    # ------------------------------------------------------------------
    async def set_latest_nav(
        self,
        fund_code: str,
        nav: Decimal,
        accumulated_nav: Decimal | None = None,
        daily_return: Decimal | None = None,
    ) -> None:
        key = f"fund:{fund_code}:nav:latest"
        mapping: dict[str, str] = {"nav": str(nav)}
        if accumulated_nav is not None:
            mapping["accumulated_nav"] = str(accumulated_nav)
        if daily_return is not None:
            mapping["daily_return"] = str(daily_return)
        async with self._lock:
            self._store[key] = _CacheEntry(mapping, ttl=300)

    async def get_latest_nav(self, fund_code: str) -> dict[str, str] | None:
        key = f"fund:{fund_code}:nav:latest"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # 30-day NAV
    # ------------------------------------------------------------------
    async def set_nav_30d(self, fund_code: str, nav_points: list[dict[str, Any]]) -> None:
        key = f"fund:{fund_code}:nav:30d"
        async with self._lock:
            self._store[key] = _CacheEntry(nav_points, ttl=3600)

    async def get_nav_30d(self, fund_code: str) -> list[dict[str, Any]]:
        key = f"fund:{fund_code}:nav:30d"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return []
            if entry.expired:
                del self._store[key]
                return []
        return entry.value

    # ------------------------------------------------------------------
    # Fund list
    # ------------------------------------------------------------------
    async def set_fund_list(self, funds: list[dict[str, Any]]) -> None:
        key = "fund:list:all"
        async with self._lock:
            self._store[key] = _CacheEntry(funds, ttl=600)

    async def get_fund_list(self) -> list[dict[str, Any]] | None:
        key = "fund:list:all"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # Hot top 20
    # ------------------------------------------------------------------
    async def set_hot_top20(self, funds: list[dict[str, Any]]) -> None:
        key = "fund:hot:top20"
        async with self._lock:
            self._store[key] = _CacheEntry(funds, ttl=600)

    async def get_hot_top20(self) -> list[dict[str, Any]] | None:
        key = "fund:hot:top20"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expired:
                del self._store[key]
                return None
        return entry.value

    # ------------------------------------------------------------------
    # Refresh time
    # ------------------------------------------------------------------
    async def set_refresh_time(self, timestamp: str) -> None:
        key = "market:refresh_time"
        async with self._lock:
            self._store[key] = _CacheEntry(timestamp, ttl=None)  # no expiry

    async def get_refresh_time(self) -> str | None:
        key = "market:refresh_time"
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
        return entry.value


# ---------------------------------------------------------------------------
# Module-level singleton (replaces the old get_redis() dependency)
# ---------------------------------------------------------------------------
_cache: CacheService | None = None


def get_cache() -> CacheService:
    """Return the module-level singleton CacheService."""
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache
```

**关键设计决策**:

| 决策 | 原因 |
|------|------|
| `asyncio.Lock` 保护 | FastAPI 是单线程异步，但 `asyncio.gather` 并发请求需要锁 |
| `time.monotonic()` 计时 | 不受系统时间调整影响，比 `datetime` 可靠 |
| TTL 值与 Redis 版保持一致 | 最新 NAV 300s, NAV 30天 3600s, 基金列表 600s, 热门 600s |
| `get_cache()` 单例模式 | 所有 Service 共享同一份缓存数据，避免重复填充 |
| 不实现 Redis ZSET 的排序能力 | `set_nav_30d` 直接存 `list[dict]`，调用方传入时已排序 |

### 3.2 `start.bat` — Windows 启动脚本

```batch
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

echo          Python: 已安装
echo          Node.js: 已安装

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
    echo          ✓ 后端初始化完成
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
    echo          ✓ 前端初始化完成
)

:: --------------------------------------------------------------------
:: Step 4: Launch backend
:: --------------------------------------------------------------------
echo.
echo [启动] 后端服务 (http://127.0.0.1:8000)...
start "预知梦基金-后端" cmd /c "cd /d %~dp0backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: Wait for backend to be ready
echo         等待后端就绪...
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
```

### 3.3 `start.sh` — Linux/macOS 启动脚本

```bash
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
```

---

## 4. 修改文件详细设计

### 4.1 `backend/app/config.py`

**当前代码 → 目标代码 diff**:

```python
# 删除
REDIS_URL: str = "redis://localhost:6379/0"

# 修改 (第 22 行)
# 旧:
DATABASE_URL: str = "postgresql+asyncpg://fund:fund123@localhost:5432/fund_db"
# 新:
DATABASE_URL: str = "sqlite+aiosqlite:///./fund_app.db"
```

**完整目标文件**:

```python
"""
Application configuration using pydantic-settings.

All settings can be overridden via environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — SQLite for single-user local deployment.
    DATABASE_URL: str = "sqlite+aiosqlite:///./fund_app.db"

    # Application
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


# Singleton settings instance
settings = Settings()
```

**变更说明**:
- 删除 `REDIS_URL` — 不再需要
- `DATABASE_URL` 默认值改为 SQLite
- `APP_HOST` 默认值改为 `127.0.0.1` (个人使用不需要监听所有接口)
- `CORS_ORIGINS` 增加 `127.0.0.1:5173` (Windows 下 localhost 解析差异)
- 删除 Docker 相关的 `localhost:80` CORS 源

### 4.2 `backend/app/database.py`

**变更要点**:
1. 删除 PostgreSQL 连接池条件分支 (SQLite 不支持 pool_size/max_overflow)
2. `init_db()` 已经是 `Base.metadata.create_all`，无需改动
3. 添加 SQLite 特有的 `connect_args`

**目标文件**:

```python
"""
Async SQLAlchemy database engine, session factory, and dependency.

Uses SQLite + aiosqlite for single-user local deployment.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# SQLite 引擎 — 单文件数据库，无需连接池
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def init_db() -> None:
    """Create all tables if they don't exist (idempotent)."""
    import app.models  # noqa: F401 — ensure all models are registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

### 4.3 `backend/app/main.py`

**变更**: 从 lifespan 中移除 `init_redis()` / `close_redis()` 和 `init_scheduler()` / `shutdown_scheduler()`。

**目标 lifespan**:

```python
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    # Startup
    await init_db()

    yield

    # Shutdown — nothing to clean up (SQLite closes with engine)
```

其余部分不变 (CORS middleware、API router、exception handler、health check)。

**注意**: Phase 1 暂时移除 APScheduler 的初始化。如果需要保留定时任务，可以在 Phase 2 重新接入按需拉取版本。实际上，对于个人使用，手动触发数据刷新 (`POST /api/v1/data/trigger-refresh`) 已足够，定时后台任务在 Phase 1 移除后不影响核心功能。

### 4.4 `backend/app/api/dependencies.py`

```python
"""
Common FastAPI dependencies.

Re-exports the most frequently used dependency-injection callables.
"""

from app.database import get_db

__all__ = ["get_db"]
```

仅删除 `get_redis` 的导入和导出。

### 4.5 `backend/app/services/cache_service.py`

**策略**: 用新写的 `backend/app/cache.py` **替换**此文件的内容。文件名保持不变（让所有 `import` 路径不变），但内部实现完全改为内存缓存。

**操作**: 用上面 [3.1](#31-backendappcachepy--内存-ttl-缓存) 的新代码覆盖此文件。原来的序列化辅助函数 (`_CacheEncoder`, `_serialize`, `_deserialize`) 也一并移入此文件。

**外部接口对比**:

| 方法 | 旧 (Redis) | 新 (内存) | 签名兼容? |
|------|-----------|-----------|:---:|
| `CacheService.__init__` | `(self, redis: Redis)` | `(self)` | ❌ |
| `set_latest_nav` | 同 | 同 | ✅ |
| `get_latest_nav` | 同 | 同 | ✅ |
| `set_nav_30d` | 同 (ZSET) | 同 (list) | ✅ |
| `get_nav_30d` | 同 | 同 | ✅ |
| `set_fund_list` | 同 | 同 | ✅ |
| `get_fund_list` | 同 | 同 | ✅ |
| `set_hot_top20` | 同 | 同 | ✅ |
| `get_hot_top20` | 同 | 同 | ✅ |
| `set_refresh_time` | 同 | 同 | ✅ |
| `get_refresh_time` | 同 | 同 | ✅ |

**构造函数签名变化是唯一的 breaking change**，需要同步修改所有创建 `CacheService` 的地方。

### 4.6 三个 Service 文件 (fund / holding / dashboard)

**变更模式相同** — 只改构造函数:

#### `backend/app/services/fund_service.py`

```python
# 删除
from redis.asyncio import Redis

# 修改 __init__
# 旧:
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
# 新:
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

#### `backend/app/services/holding_service.py`

```python
# 删除
from redis.asyncio import Redis

# 修改 __init__
# 旧:
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
# 新:
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

#### `backend/app/services/dashboard_service.py`

```python
# 删除
from redis.asyncio import Redis

# 修改 __init__
# 旧:
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
# 新:
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

### 4.7 六个 API 路由文件

**变更模式相同** — 删除 `Redis` 导入和 `get_redis` 依赖注入参数:

#### `backend/app/api/funds.py`

```python
# 删除以下行:
from redis.asyncio import Redis
from app.api.dependencies import get_db, get_redis  # → 改为 from app.api.dependencies import get_db

# 所有路由函数中删除:
#   redis: Redis = Depends(get_redis),
# 以及对应的 Service 构造参数:
#   service = FundService(db, redis)  # → service = FundService(db)
```

**涉及路由函数** (每个都要改):
- `search` (line 37)
- `filter_funds` (line 73)
- `compare` (line 116)
- `get_detail` (line 143)
- `get_nav_history` (line 169)
- `get_portfolio` (line 188)

#### `backend/app/api/holdings.py`

涉及 5 个路由函数:
- `create_holding` (line 36)
- `list_holdings` (line 54)
- `get_holding` (line 76)
- `update_holding` (line 102)
- `delete_holding` (line 127)

#### `backend/app/api/dashboard.py`

涉及 4 个路由函数:
- `get_summary` (line 30)
- `get_returns_chart` (line 52)
- `get_allocation` (line 70)
- `get_risk_metrics` (line 88)

#### `backend/app/api/watchlist.py`

涉及 3 个路由函数:
- `list_watchlist` (line 33)
- `add_to_watchlist` (line 52)
- `remove_from_watchlist` (line 74)

#### `backend/app/api/ocr.py`

涉及 1 个路由函数:
- `confirm_ocr` (line 114)

#### `backend/app/api/data_mgmt.py`

特殊处理 — 此文件直接使用 `get_redis` 创建 `CacheService`:

```python
# 删除:
from redis.asyncio import Redis
from app.api.dependencies import get_redis

# 改为:
from app.services.cache_service import CacheService, get_cache

# get_refresh_status 函数签名:
# 旧: async def get_refresh_status(redis: Redis = Depends(get_redis)) -> dict[str, Any]:
# 新: async def get_refresh_status() -> dict[str, Any]:
#      cache = get_cache()
```

### 4.8 `backend/app/scheduler/jobs.py`

**变更**: 删除对 `app.redis_client.get_redis` 的依赖，改为使用 `get_cache()`。

```python
# 删除:
from app.redis_client import get_redis

# 改为:
from app.services.cache_service import CacheService, get_cache
```

**在 3 处修改**:

1. `fetch_market_data()` 的 Step 6 (line ~182):
```python
# 旧:
redis = await get_redis()
cache = CacheService(redis)
# 新:
cache = get_cache()
```

2. `fetch_fund_list_daily()` 的缓存更新 (line ~253):
```python
# 旧:
redis = await get_redis()
cache = CacheService(redis)
# 新:
cache = get_cache()
```

3. `CacheService(redis)` → `CacheService()` (已由 get_cache() 替代)

**注意**: Phase 1 中 scheduler 本身会被保留但**不自动启动** (main.py 的 lifespan 中已移除 `init_scheduler()` 调用)。`jobs.py` 的修改是为了**编译通过**，确保所有导入路径有效。实际上 Phase 2 会整体删除此模块。

### 4.9 `backend/requirements.txt`

```txt
# Core Framework
fastapi>=0.110.0
uvicorn[standard]>=0.27.0

# Database — SQLite for single-user deployment
sqlalchemy[asyncio]>=2.0.25
aiosqlite>=0.19.0

# Validation & Settings
pydantic>=2.5.0
pydantic-settings>=2.1.0

# HTTP Client (for external API calls)
httpx>=0.26.0

# Data Processing
pandas>=2.1.0
numpy>=1.26.0

# File Uploads
python-multipart>=0.0.6
```

**变更**:

| 包 | 旧 | 新 | 原因 |
|----|----|----|------|
| `asyncpg` | ✅ | ❌ | PostgreSQL 驱动，不再需要 |
| `alembic` | ✅ | ❌ | SQLite 用 `Base.metadata.create_all`，不需要迁移 |
| `redis` | ✅ | ❌ | 改用内存缓存 |
| `apscheduler` | ✅ | ❌ | Phase 1 移除定时调度 |
| `aiosqlite` | ❌ | ✅ | SQLite 异步驱动 |

依赖数量: 15 → 9 (减少 40%)

### 4.10 `backend/.env`

```env
# 预知梦基金 — 本地开发环境变量
# 所有配置都有合理默认值，此文件可留空

# 可选: 覆盖数据库路径 (默认 ./fund_app.db)
# DATABASE_URL=sqlite+aiosqlite:///./fund_app.db

# 可选: 开启调试模式
# APP_DEBUG=true
```

之前的内容 `DATABASE_URL=sqlite+aiosqlite:///./fund_app.db` 和 `REDIS_URL=...` 均删除 — `config.py` 已有相同的默认值。

### 4.11 `README.md`

完全重写，参照 `fund-recommend_refe` 的简洁风格:

```markdown
# 预知梦基金 (Prophetic Dream Fund)

面向个人投资者的基金投研工具 — 基金查询、持仓管理、OCR 识别、智能推荐、回测分析。

## 快速开始

### 前置依赖

- **Python** 3.11+
- **Node.js** 18+

### 启动

```bash
# Windows — 双击运行
start.bat

# Linux / macOS
chmod +x start.sh
./start.sh
```

浏览器打开 `http://localhost:5173` 即可使用。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy (async) / SQLite |
| 前端 | TypeScript / React 18 / Ant Design / Vite |
| 数据 | SQLite (单文件，零配置) |

## 功能

- **持仓管理** — 手动录入 / OCR 截图导入，实时盈亏计算
- **市场行情** — 基金搜索、筛选、对比、净值走势图
- **智能推荐** — 多因子打分、风险匹配、择时信号、组合优化
- **历史回测** — 多策略回测、月度再平衡、收益归因
- **仪表盘** — 资产总览、收益曲线、配置饼图、风险指标
- **数据管理** — 多数据源 (天天基金/东方财富)、交叉验证、手动刷新

## 项目结构

```
prophetic-dream-fund/
├── start.bat                  # Windows 一键启动
├── start.sh                   # Linux/macOS 一键启动
├── README.md
├── backend/                   # FastAPI 后端
│   ├── requirements.txt
│   ├── .env
│   └── app/
│       ├── main.py            # 入口
│       ├── config.py          # 配置
│       ├── database.py        # 数据库
│       ├── api/               # API 路由
│       ├── models/            # 数据模型
│       ├── schemas/           # Pydantic Schema
│       ├── services/          # 业务逻辑
│       ├── adapters/          # 外部数据源
│       ├── engine/            # 推荐引擎
│       └── utils/             # 工具函数
└── frontend/                  # React 前端
    ├── package.json
    └── src/
        ├── api/               # API 调用层
        ├── components/        # 通用组件
        ├── pages/             # 页面
        ├── stores/            # Zustand 状态
        ├── types/             # TypeScript 类型
        └── utils/             # 工具函数
```

## 许可证

[MIT](LICENSE)
```

---

## 5. 数据流变化

### 重构前

```
API 请求 → Service(db, redis) → CacheService(redis)
                  │                      │
                  ▼                      ▼
           PostgreSQL              Redis (缓存命中)
           (持久化)                PostgreSQL (缓存未命中)
```

### 重构后

```
API 请求 → Service(db) → CacheService() [内存]
                  │              │
                  ▼              ▼
           SQLite           内存字典 (缓存命中)
           (持久化)         SQLite (缓存未命中)
```

**性能影响分析**:

| 场景 | 重构前 (Redis) | 重构后 (内存) | 影响 |
|------|:---:|:---:|------|
| 缓存命中延迟 | ~1ms (网络往返) | ~0.001ms (内存访问) | ✅ 更快 |
| 缓存容量 | 受 Redis 内存限制 | 受进程内存限制 | → 相同 |
| 缓存持久化 | 跨进程重启保留 | 进程重启清空 | ⚠️ 冷启动多一次 DB 查询 |
| 跨进程共享 | ✅ | ❌ (只有 1 个进程) | → 无影响 |
| DB 查询延迟 (SQLite vs PG) | PG ~1ms (网络) | SQLite ~0.1ms (本地文件) | ✅ 更快 |

**结论**: 对于单用户场景，内存缓存 + SQLite **全面优于** Redis + PostgreSQL。唯一的"退化"是进程重启后缓存清空，但首次 DB 查询只需 0.1ms，对用户体验无感知影响。

---

## 6. 启动流程

### 冷启动 (首次运行)

```
用户双击 start.bat
  │
  ├─ [1] 检查 Python / Node.js 是否安装
  │
  ├─ [2] pip install -r requirements.txt    (~30s, 仅首次)
  ├─ [3] python -c "init_db()"              (~0.5s, 仅首次)
  │
  ├─ [4] npm install                         (~60s, 仅首次)
  │
  ├─ [5] uvicorn app.main:app --port 8000   (~1s)
  │       └─ init_db() → 建表
  │       └─ 监听 127.0.0.1:8000
  │
  └─ [6] npx vite --port 5173               (~1s)
          └─ 监听 127.0.0.1:5173
          └─ proxy /api → localhost:8000
```

| 阶段 | 首次 | 后续 |
|------|------|------|
| 环境检查 | < 0.5s | < 0.5s |
| 后端初始化 | ~30s | 跳过 |
| 前端初始化 | ~60s | 跳过 |
| 后端启动 | ~1s | ~1s |
| 前端启动 | ~1s | ~1s |
| **总计** | **~90s** | **~3s** |

### 热启动 (日常使用)

```
用户双击 start.bat
  │
  ├─ [1] 检查 Python / Node.js ✓
  ├─ [2] 后端初始化 → 跳过 (fund_app.db 已存在)
  ├─ [3] 前端初始化 → 跳过 (node_modules 已存在)
  ├─ [4] uvicorn 启动 → ~1s
  └─ [5] vite 启动 → ~1s

总计: < 3 秒
```

---

## 7. 兼容性与风险

### 7.1 数据库兼容性

**问题**: SQLite 不支持 PostgreSQL 的部分 SQL 语法。

**已排查的兼容性问题**:

| SQL 特性 | PostgreSQL | SQLite | 当前代码中的使用 | 状态 |
|----------|:---:|:---:|------|:---:|
| `INSERT ... ON CONFLICT DO UPDATE` | ✅ | ✅ (3.24+) | `data_ingestion_service.py` | ⚠️ 语法略有差异 |
| `ilike` | ✅ | ❌ (需改为 `LIKE`, SQLite 默认不区分大小写) | `fund_service.py` | ⚠️ 需修改 |
| `func.row_number()` | ✅ | ✅ | `fund_service.py` | ✅ |
| `CASCADE` 外键 | ✅ | ✅ (需 `PRAGMA foreign_keys=ON`) | 所有 models | ⚠️ 需开启 PRAGMA |
| `JSON` 列类型 | ✅ `JSONB` | ✅ `JSON` (文本存储) | `recommendation.py` | ⚠️ 查询方式不同 |
| `BigInteger` | ✅ | ✅ `INTEGER` | 多个 model | ✅ |
| `Decimal` → `NUMERIC` | ✅ | ✅ | 多个 model | ✅ |
| 连接池 | ✅ | ❌ (不需要) | `database.py` | ✅ 已处理 |

**需要额外处理的细节** (Phase 1 实现时注意):

#### a. `ilike` → `like`
```python
# fund_service.py: 将 Fund.code.ilike(pattern) 改为 Fund.code.like(pattern)
# SQLite 的 LIKE 对 ASCII 默认不区分大小写，且我们已在代码中用 .lower() 预处理
```

#### b. SQLite 外键约束
```python
# database.py — init_db() 之后添加:
async def init_db() -> None:
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite 默认不启用外键约束，需要手动开启
        if "sqlite" in settings.DATABASE_URL:
            await conn.execute(text("PRAGMA foreign_keys=ON"))
```

#### c. `INSERT ... ON CONFLICT` (UPSERT)
```python
# data_ingestion_service.py 中如有:
# INSERT INTO funds (...) VALUES (...) ON CONFLICT (code) DO UPDATE SET ...
# SQLite 语法: INSERT OR REPLACE INTO ... 或 INSERT ... ON CONFLICT(code) DO UPDATE SET ...
# SQLite 3.24+ 支持 ON CONFLICT，但需要 code 有 UNIQUE 约束 (已在 model 中定义)
```

### 7.2 数据类型兼容性

SQLAlchemy ORM 层抽象了大部分差异。以下类型的映射已确认:

| Python | SQLAlchemy Type | PostgreSQL | SQLite |
|--------|----------------|------------|--------|
| `Decimal` | `NUMERIC` | `NUMERIC` | `NUMERIC` |
| `int` | `BigInteger` | `BIGINT` | `INTEGER` |
| `str` | `String` | `VARCHAR` | `TEXT` |
| `date` | `Date` | `DATE` | `TEXT` (ISO format) |
| `datetime` | `DateTime` | `TIMESTAMP` | `TEXT` (ISO format) |
| `bool` | `Boolean` | `BOOLEAN` | `INTEGER` (0/1) |
| `dict` | `JSON` | `JSONB` | `TEXT` (JSON string) |

**JSON 列的特殊处理**:
- `recommendation.py` 的 `RecommendationLog.reasons` 字段类型是 `JSON`
- SQLite 将其存储为 TEXT，SQLAlchemy 自动序列化/反序列化
- 查询 JSON 内部字段时 (`func.json_extract`) 在 SQLite 中需改为 `json_extract` 函数

### 7.3 回滚策略

如果 Phase 1 出现问题，回滚方式:
1. `git checkout` 恢复所有修改文件
2. 或者重新 `docker compose up -d`（如果尚未删除 Docker 配置）
3. SQLite 数据库文件 (`fund_app.db`) 可以随时删除重建

### 7.4 测试策略

Phase 1 完成后需手动验证:

| 测试场景 | 验证步骤 |
|----------|----------|
| 冷启动 | 删除 `fund_app.db` 和 `node_modules`，运行 `start.bat` |
| 热启动 | 再次运行 `start.bat`，确认 < 5s 可用 |
| 持仓 CRUD | 创建/查看/编辑/删除一条持仓 |
| 基金搜索 | 搜索 "华夏"，验证结果 |
| 基金详情 | 点击任一基金，验证净值图表加载 |
| 仪表盘 | 验证首页汇总卡片、饼图、收益曲线 |
| 推荐引擎 | 完成风险问卷，获取推荐列表 |
| 数据刷新 | 触发手动刷新，确认无报错 |
| OCR | 上传一张基金截图 (如有 PaddleOCR) |
| 进程清理 | 关闭终端窗口，确认两个进程均退出 |

---

## 附录 A: Redis 引用完整列表

以下是当前引用 Redis 的**全部位置**及 Phase 1 处理方式:

| # | 文件 | 行 | 引用内容 | 处理 |
|---|------|----|---------|------|
| 1 | `main.py` | 18 | `from app.redis_client import ...` | 删除 |
| 2 | `main.py` | 30,35,42 | `init_redis()`, `close_redis()` | 删除 |
| 3 | `config.py` | 24-25 | `REDIS_URL` | 删除 |
| 4 | `redis_client.py` | 全文件 | — | 删除文件 |
| 5 | `dependencies.py` | 9,11 | `get_redis` | 删除 |
| 6 | `cache_service.py` | 16,57,59,60 | `from redis.asyncio import Redis` | 重写文件 |
| 7 | `fund_service.py` | 15,45,47 | `Redis` 导入 + 构造函数 | 删除导入, 改构造函数 |
| 8 | `holding_service.py` | 14,28,30 | `Redis` 导入 + 构造函数 | 删除导入, 改构造函数 |
| 9 | `dashboard_service.py` | 15,43,45 | `Redis` 导入 + 构造函数 | 删除导入, 改构造函数 |
| 10 | `scheduler/jobs.py` | 4,19,61,179-217 | `get_redis` 导入 + 使用 | 改为 `get_cache()` |
| 11 | `api/funds.py` | 13,16 | `Redis` 导入 | 删除 |
| 12 | `api/funds.py` | 37,40,73,95,116,127,143,146,169,172,188,191 | 6 个路由的 Redis 参数 | 删除 |
| 13 | `api/holdings.py` | 13,16 | `Redis` 导入 | 删除 |
| 14 | `api/holdings.py` | 36,39,54,57,76,79,102,105,127,130 | 5 个路由的 Redis 参数 | 删除 |
| 15 | `api/dashboard.py` | 13,16 | `Redis` 导入 | 删除 |
| 16 | `api/dashboard.py` | 30,33,52,55,70,73,88,91 | 4 个路由的 Redis 参数 | 删除 |
| 17 | `api/watchlist.py` | 13,16 | `Redis` 导入 | 删除 |
| 18 | `api/watchlist.py` | 33,36,52,58,74,77 | 3 个路由的 Redis 参数 | 删除 |
| 19 | `api/ocr.py` | 16,19 | `Redis` 导入 | 删除 |
| 20 | `api/ocr.py` | 114,124 | `redis` 参数 + Service 构造 | 删除 |
| 21 | `api/data_mgmt.py` | 13,16,17 | `Redis` 导入 | 改为 `get_cache` |
| 22 | `api/data_mgmt.py` | 60,62 | `redis` 参数 + 创建 CacheService | 改为 `get_cache()` |
| 23 | `services/__init__.py` | 5,8 | 注释 + 导入 | 更新注释 |

共计 **23 处**需要修改或删除，涉及 **19 个文件**。

---

## 附录 B: Phase 2 预览

Phase 1 完成后，Phase 2 将进一步简化:

1. **APScheduler → 按需拉取** — 删除 `backend/app/scheduler/` 整个模块
2. **删除 Tushare 适配器** — `backend/app/adapters/tushare.py`
3. **简化 normalizer/cross_validator** — 从 2-4 源简化到 2 源
4. **删除 Alembic 目录** — `backend/alembic/` + `backend/alembic.ini`
5. **依赖清理** — `requirements.txt` 最终减少到 ~6 个核心包
6. **FastAPI serve 前端静态文件** — 单进程部署选项

---

*设计文档版本: v1.0*
*最后更新: 2026-06-28*
