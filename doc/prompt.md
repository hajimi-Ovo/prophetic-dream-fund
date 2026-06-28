# Phase 1 轻量化重构 — 分模块子 Agent 执行指南

> **项目根目录**: `D:\桌面\test\prophetic-dream-fund`
> **目标**: 去除 Docker / PostgreSQL / Redis，改用 SQLite + 内存缓存 + 一键启动
> **调度策略**: 8 个模块文件互不重叠，可全并行派发；全部完成后运行集成验证

---

## 目录

1. [总览：模块依赖图](#1-总览模块依赖图)
2. [全局约束 (每个 Agent 必须遵守)](#2-全局约束-每个-agent-必须遵守)
3. [Module A — 清理：删除 Docker + Redis 文件](#3-module-a--清理删除-docker--redis-文件)
4. [Module B — 基础设施：数据库 + 配置 + 依赖](#4-module-b--基础设施数据库--配置--依赖)
5. [Module C — 缓存层：内存 TTL 缓存重写](#5-module-c--缓存层内存-ttl-缓存重写)
6. [Module D — 入口：main.py + dependencies.py](#6-module-d--入口mainpy--dependenciespy)
7. [Module E — 服务层：3 个 Service 构造函数去 Redis](#7-module-e--服务层3-个-service-构造函数去-redis)
8. [Module F — 调度器：scheduler/jobs.py 适配](#8-module-f--调度器schedulerjobspy-适配)
9. [Module G — API 层：6 个路由文件去 Redis 注入](#9-module-g--api-层6-个路由文件去-redis-注入)
10. [Module H — 文档：README + 启动脚本](#10-module-h--文档readme--启动脚本)
11. [集成验证 (所有 Module 完成后执行)](#11-集成验证-所有-module-完成后执行)

---

## 1. 总览：模块依赖图

```
Wave 1 (全部并行，文件无冲突)
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Module A │  │ Module B │  │ Module C │  │ Module H │
│ 清理 8文件│  │ 基础设施  │  │ 缓存重写  │  │ 文档脚本  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                  ▼
Wave 2    ┌──────────┐  ┌──────────┐       ┌──────────┐
(全并行)   │ Module D │  │ Module E │       │ Module G │
          │ 入口改造  │  │ 服务层改造│       │ API层改造 │
          └──────────┘  └──────────┘       └──────────┘
                                │
              ┌─────────────────┘
              ▼
Wave 2    ┌──────────┐
          │ Module F │
          │ 调度器适配│
          └──────────┘

全部完成 → 集成验证
```

**文件冲突检查**:

| 文件 | Module |
|------|--------|
| `docker-compose.yml` 等 7 个 Docker 文件 | A |
| `backend/app/redis_client.py` | A |
| `backend/app/config.py` | B |
| `backend/app/database.py` | B |
| `backend/requirements.txt` | B |
| `backend/.env` | B |
| `backend/app/services/cache_service.py` | C |
| `backend/app/main.py` | D |
| `backend/app/api/dependencies.py` | D |
| `backend/app/services/fund_service.py` | E |
| `backend/app/services/holding_service.py` | E |
| `backend/app/services/dashboard_service.py` | E |
| `backend/app/scheduler/jobs.py` | F |
| `backend/app/api/funds.py` | G |
| `backend/app/api/holdings.py` | G |
| `backend/app/api/dashboard.py` | G |
| `backend/app/api/watchlist.py` | G |
| `backend/app/api/ocr.py` | G |
| `backend/app/api/data_mgmt.py` | G |
| `README.md` | H |
| `start.bat` | H |
| `start.sh` | H |

✅ **零文件冲突 — 8 个 Module 全部可以并行执行。**

---

## 2. 全局约束 (每个 Agent 必须遵守)

当你作为子 Agent 收到以下任一 Module 的任务时，请严格遵守:

1. **不要修改前端代码** — `frontend/` 目录下的文件一个都不要动
2. **不要修改测试文件** — `backend/tests/` 目录不动
3. **不要修改 Engine 模块** — `backend/app/engine/` 下的任何文件不动 (fund_ranker / risk_scorer / timing_advisor / portfolio_builder / backtester)
4. **不要修改数据模型** — `backend/app/models/` 不动
5. **不要修改 Pydantic Schema** — `backend/app/schemas/` 不动
6. **不要修改适配器** — `backend/app/adapters/` 不动 (Phase 2 才精简)
7. **保持 API 接口签名不变** — URL、HTTP method、request/response body 的 JSON 结构不变
8. **只做你的 Module 范围内的事** — 不要跨模块修改
9. **完成任务后报告** — 列出你修改了哪些文件，每个文件做了什么变更

---

## 3. Module A — 清理：删除 Docker + Redis 文件

### 角色
你是清理专家。你的唯一任务是删除不再需要的文件。

### 任务
删除以下 **8 个文件**:

```
D:\桌面\test\prophetic-dream-fund\docker-compose.yml
D:\桌面\test\prophetic-dream-fund\nginx.conf
D:\桌面\test\prophetic-dream-fund\backend\Dockerfile
D:\桌面\test\prophetic-dream-fund\backend\.dockerignore
D:\桌面\test\prophetic-dream-fund\frontend\Dockerfile
D:\桌面\test\prophetic-dream-fund\frontend\.dockerignore
D:\桌面\test\prophetic-dream-fund\frontend\nginx.conf
D:\桌面\test\prophetic-dream-fund\backend\app\redis_client.py
```

### 验证
删除完成后，逐一确认以上 8 个路径全部不存在。

### 完成后报告模板
```
[Module A] 完成
- 已删除 7 个 Docker 相关文件
- 已删除 backend/app/redis_client.py
- 验证: 8 个文件全部不存在 ✓
```

---

## 4. Module B — 基础设施：数据库 + 配置 + 依赖

### 角色
你是后端基础设施工程师。你需要将数据库层从 PostgreSQL 切换到 SQLite，并更新所有相关配置。

### 任务清单

#### B1. 重写 `backend/app/config.py`

用以下完整内容覆盖文件:

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

#### B2. 重写 `backend/app/database.py`

用以下完整内容覆盖文件:

```python
"""
Async SQLAlchemy database engine, session factory, and dependency.

Uses SQLite + aiosqlite for single-user local deployment.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# SQLite engine — single-file database, no connection pool needed
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    connect_args={"check_same_thread": False},
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
        # SQLite does not enforce foreign keys by default
        await conn.execute(text("PRAGMA foreign_keys=ON"))
    logger.info("Database tables created/verified")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

#### B3. 重写 `backend/requirements.txt`

用以下完整内容覆盖文件:

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

#### B4. 重写 `backend/.env`

用以下完整内容覆盖文件:

```env
# 预知梦基金 — 本地开发环境变量
# 所有配置都有合理默认值，此文件可留空

# 可选: 覆盖数据库路径 (默认 ./fund_app.db)
# DATABASE_URL=sqlite+aiosqlite:///./fund_app.db

# 可选: 开启调试模式
# APP_DEBUG=true
```

### 关键变更说明
- `config.py`: 删除 `REDIS_URL`，`DATABASE_URL` 改为 SQLite 默认值，`APP_HOST` 改为 `127.0.0.1`
- `database.py`: 删除 PostgreSQL 连接池分支，添加 `check_same_thread=False` 和 `PRAGMA foreign_keys=ON`
- `requirements.txt`: 删除 `asyncpg`, `alembic`, `redis`, `apscheduler`；新增 `aiosqlite`
- `.env`: 最小化，只保留注释说明

### 验证
- 4 个文件保存后无语法错误
- `requirements.txt` 中不存在 `asyncpg`, `alembic`, `redis`, `apscheduler`
- `config.py` 中不存在 `REDIS_URL`

### 完成后报告模板
```
[Module B] 完成
- config.py: 删除 REDIS_URL，DATABASE_URL 改 SQLite
- database.py: 移除 PG 连接池，添加 SQLite PRAGMA
- requirements.txt: 删除 4 个包，新增 aiosqlite
- .env: 最小化
- 验证: 4 个文件就绪 ✓
```

---

## 5. Module C — 缓存层：内存 TTL 缓存重写

### 角色
你是缓存模块工程师。你需要把 Redis 缓存替换为等价的纯内存实现。

### 任务
用以下完整内容覆盖 `D:\桌面\test\prophetic-dream-fund\backend\app\services\cache_service.py`:

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
# JSON encoder
# ---------------------------------------------------------------------------
class _CacheEncoder(json.JSONEncoder):
    """Custom encoder: Decimal → str, date/datetime → isoformat."""

    def default(self, obj: object) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, date | datetime):
            return obj.isoformat()
        return super().default(obj)


def _serialize(value: Any) -> str:
    """JSON-dump *value* using the cache-aware encoder."""
    return json.dumps(value, cls=_CacheEncoder, ensure_ascii=False)


def _deserialize(text: str | bytes | None) -> Any:
    """JSON-load *text*; returns None on empty or parse failure."""
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
            self._store[key] = _CacheEntry(timestamp, ttl=None)

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

### 关键变更说明
- `CacheService.__init__()` 不再接受 `redis: Redis` 参数，改为无参构造
- 底层存储从 Redis 命令改为 `dict[str, _CacheEntry]` + `asyncio.Lock`
- TTL 过期用 `time.monotonic()` 实现，与 Redis 版 TTL 值一致
- 新增 `get_cache()` 模块级单例函数，替代全局的 `get_redis()`
- 所有 10 个 public 方法签名不变（除构造函数）

### 验证
- 文件保存后无语法错误
- 文件中不存在 `import redis` 或 `from redis`
- `CacheService.__init__` 签名为 `def __init__(self) -> None:`
- `get_cache()` 函数存在

### 完成后报告模板
```
[Module C] 完成
- 重写 cache_service.py: Redis → 内存 dict + asyncio.Lock
- TTL 值: NAV 300s / NAV 30d 3600s / fund_list 600s / hot_top20 600s
- 新增 get_cache() 单例函数
- 验证: 无 Redis 依赖 ✓
```

---

## 6. Module D — 入口：main.py + dependencies.py

### 角色
你是应用入口工程师。你需要清理 `main.py` 的 lifespan 和 `dependencies.py` 中的 Redis 引用。

### 任务

#### D1. 修改 `backend/app/main.py`

先读取该文件，然后做以下精确修改:

**修改 1** — 删除这两行 import:
```python
from app.redis_client import close_redis, init_redis
from app.scheduler import init_scheduler, shutdown_scheduler
```

**修改 2** — 将整个 `lifespan` 函数替换为:
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan handler — init DB on startup."""
    # Startup
    await init_db()

    yield

    # Shutdown — nothing to clean up (SQLite closes with engine)
```

**不需要改动**的部分:
- `from contextlib import asynccontextmanager` (保留)
- `FastAPI(...)` 构造函数
- `app.add_middleware(...)` CORS 配置
- `app.include_router(...)` 路由挂载
- `@app.exception_handler(Exception)` 异常处理
- `@app.get("/health")` 健康检查

#### D2. 重写 `backend/app/api/dependencies.py`

用以下完整内容覆盖文件:

```python
"""
Common FastAPI dependencies.

Re-exports the most frequently used dependency-injection callables.
"""

from app.database import get_db

__all__ = ["get_db"]
```

### 验证
- `main.py` 中不存在 `init_redis`, `close_redis`, `init_scheduler`, `shutdown_scheduler` 引用
- `main.py` 中不存在 `from app.redis_client` 和 `from app.scheduler`
- `dependencies.py` 中只导出 `get_db`，不存在 `get_redis`

### 完成后报告模板
```
[Module D] 完成
- main.py: lifespan 只保留 init_db()，删除 Redis/Scheduler 初始化和清理
- dependencies.py: 删除 get_redis 导出
- 验证: 无残留引用 ✓
```

---

## 7. Module E — 服务层：3 个 Service 构造函数去 Redis

### 角色
你是业务服务工程师。你需要修改 3 个 Service 类，去掉它们构造函数中的 Redis 参数。

### 通用操作模式
对每个文件做完全相同的两步:
1. 删除 `from redis.asyncio import Redis` 这一行
2. 修改 `__init__` 方法：去掉 `redis: Redis` 参数，`CacheService(redis)` 改为 `CacheService()`

---

### E1. `backend/app/services/fund_service.py`

**Step 1** — 删除这一行:
```python
from redis.asyncio import Redis
```

**Step 2** — 找到构造函数，将:
```python
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
```
改为:
```python
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

**注意**: 文件其余部分不要改动。`CacheService` 的 import 来自 `from app.services.cache_service import CacheService`，这个路径不变。

---

### E2. `backend/app/services/holding_service.py`

**Step 1** — 删除这一行:
```python
from redis.asyncio import Redis
```

**Step 2** — 将构造函数:
```python
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
```
改为:
```python
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

---

### E3. `backend/app/services/dashboard_service.py`

**Step 1** — 删除这一行:
```python
from redis.asyncio import Redis
```

**Step 2** — 将构造函数:
```python
def __init__(self, db: AsyncSession, redis: Redis) -> None:
    self.db = db
    self.cache = CacheService(redis)
```
改为:
```python
def __init__(self, db: AsyncSession) -> None:
    self.db = db
    self.cache = CacheService()
```

---

### 验证
在 3 个文件中搜索以下字符串，确保全部不存在:
- `from redis.asyncio import Redis`
- `redis: Redis`
- `CacheService(redis)`

### 完成后报告模板
```
[Module E] 完成
- fund_service.py: __init__ 去掉 redis 参数
- holding_service.py: __init__ 去掉 redis 参数
- dashboard_service.py: __init__ 去掉 redis 参数
- 验证: 3 个文件均无 Redis 引用 ✓
```

---

## 8. Module F — 调度器：scheduler/jobs.py 适配

### 角色
你是调度模块工程师。你需要把 `jobs.py` 中的 Redis 缓存调用改为内存缓存。

### 任务

读取 `D:\桌面\test\prophetic-dream-fund\backend\app\scheduler\jobs.py`，做以下修改:

#### 修改 1 — 替换导入
删除:
```python
from app.redis_client import get_redis
```
改为:
```python
from app.services.cache_service import get_cache
```

#### 修改 2 — `fetch_market_data()` 函数中
找到 Step 6 附近的这段代码:
```python
redis = await get_redis()
cache = CacheService(redis)
```
替换为:
```python
cache = get_cache()
```

#### 修改 3 — `fetch_fund_list_daily()` 函数中
同样找到:
```python
redis = await get_redis()
cache = CacheService(redis)
```
替换为:
```python
cache = get_cache()
```

#### 修改 4 (可选) — 更新文件头部注释
文件头部注释中提到了 "Redis connection"，如果你看到类似这句:
```
Each job creates its own DB session and Redis connection so that
```
改为:
```
Each job creates its own DB session so that
```

### 注意
- 这个文件在 Phase 1 中**不会被 main.py 调用**（Module D 已经移除了 lifespan 中的 scheduler 初始化）
- 修改只是为了确保代码能编译通过，为 Phase 2 的完整删除做准备
- 不需要修改 `CacheService` 的 import（它已经从 `app.services.cache_service` 导入）

### 验证
- 文件中不存在 `get_redis` 或 `from app.redis_client`
- 文件中不存在 `CacheService(redis)` (应该都改为 `get_cache()`)

### 完成后报告模板
```
[Module F] 完成
- jobs.py: get_redis → get_cache (2 处)
- 验证: 无 Redis 引用 ✓
```

---

## 9. Module G — API 层：6 个路由文件去 Redis 注入

### 角色
你是 API 路由工程师。你需要从 6 个 API 路由文件中删除所有 Redis 依赖注入。

### 通用操作模式
对每个文件:
1. 删除 `from redis.asyncio import Redis` 导入行
2. 修改 `from app.api.dependencies import get_db, get_redis` → `from app.api.dependencies import get_db`
3. 在每个路由函数签名中删除 `redis: Redis = Depends(get_redis),` 参数
4. 将对应的 `XxxService(db, redis)` 调用改为 `XxxService(db)`

---

### G1. `backend/app/api/funds.py`

涉及 **6 个路由函数**，每个都做同样的修改:

| 函数 | 删除参数 | Service 构造改动 |
|------|----------|-----------------|
| `search` | `redis: Redis = Depends(get_redis),` | `FundService(db, redis)` → `FundService(db)` |
| `filter_funds` | 同上 | 同上 |
| `compare` | 同上 | 同上 |
| `get_detail` | 同上 | 同上 |
| `get_nav_history` | 同上 | 同上 |
| `get_portfolio` | 同上 | 同上 |

**操作步骤**:
1. 读取文件
2. 删除 `from redis.asyncio import Redis`
3. `from app.api.dependencies import get_db, get_redis` → `from app.api.dependencies import get_db`
4. 逐个函数删除 `redis` 参数和修改 Service 调用
5. 搜索 `redis` 确认无残留

---

### G2. `backend/app/api/holdings.py`

涉及 **5 个路由函数**:

| 函数 | 删除参数 | Service 构造改动 |
|------|----------|-----------------|
| `create_holding` | `redis: Redis = Depends(get_redis),` | `HoldingService(db, redis)` → `HoldingService(db)` |
| `list_holdings` | 同上 | 同上 |
| `get_holding` | 同上 | 同上 |
| `update_holding` | 同上 | 同上 |
| `delete_holding` | 同上 | 同上 |

---

### G3. `backend/app/api/dashboard.py`

涉及 **4 个路由函数**:

| 函数 | 删除参数 | Service 构造改动 |
|------|----------|-----------------|
| `get_summary` | `redis: Redis = Depends(get_redis),` | `DashboardService(db, redis)` → `DashboardService(db)` |
| `get_returns_chart` | 同上 | 同上 |
| `get_allocation` | 同上 | 同上 |
| `get_risk_metrics` | 同上 | 同上 |

---

### G4. `backend/app/api/watchlist.py`

涉及 **3 个路由函数**:

| 函数 | 删除参数 | Service 构造改动 |
|------|----------|-----------------|
| `list_watchlist` | `redis: Redis = Depends(get_redis),` | `HoldingService(db, redis)` → `HoldingService(db)` |
| `add_to_watchlist` | 同上 | 同上 |
| `remove_from_watchlist` | 同上 | 同上 |

---

### G5. `backend/app/api/ocr.py`

涉及 **1 个路由函数**:

| 函数 | 删除参数 | Service 构造改动 |
|------|----------|-----------------|
| `confirm_ocr` | `redis: Redis = Depends(get_redis),` | `HoldingService(db, redis)` → `HoldingService(db)` |

---

### G6. `backend/app/api/data_mgmt.py` ⚠️ 特殊处理

这个文件与其他 5 个不同 — 它直接用 `get_redis` 创建 `CacheService`，不通过 Service 类。

**操作步骤**:
1. 删除 `from redis.asyncio import Redis`
2. 删除 `from app.api.dependencies import get_redis`（如果存在）
3. 添加 `from app.services.cache_service import get_cache`
4. 在 `get_refresh_status` 函数中:
   - 删除函数签名中的 `redis: Redis = Depends(get_redis)`
   - 将 `cache = CacheService(redis)` 改为 `cache = get_cache()`

---

### 验证
在全部 6 个 API 文件中搜索以下字符串:
- `from redis.asyncio import Redis` — 应全部不存在
- `get_redis` — 应全部不存在
- `CacheService(redis)` — 应全部不存在

### 完成后报告模板
```
[Module G] 完成
- funds.py: 6 个路由去 Redis ✓
- holdings.py: 5 个路由去 Redis ✓
- dashboard.py: 4 个路由去 Redis ✓
- watchlist.py: 3 个路由去 Redis ✓
- ocr.py: 1 个路由去 Redis ✓
- data_mgmt.py: get_redis → get_cache ✓
- 验证: 6 个文件均无 Redis 残留 ✓
```

---

## 10. Module H — 文档：README + 启动脚本

### 角色
你是文档与 DevOps 工程师。你需要创建新的 README 和启动脚本。

### 任务清单

#### H1. 重写 `README.md`

用以下完整内容覆盖 `D:\桌面\test\prophetic-dream-fund\README.md`:

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

#### H2. 创建 `start.bat`

新建文件 `D:\桌面\test\prophetic-dream-fund\start.bat`:

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

#### H3. 创建 `start.sh`

新建文件 `D:\桌面\test\prophetic-dream-fund\start.sh`:

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

### 验证
- `README.md` 已更新，不再提及 Docker/PostgreSQL/Redis
- `start.bat` 存在且内容完整
- `start.sh` 存在且内容完整
- Linux/Mac 用户需手动执行 `chmod +x start.sh`

### 完成后报告模板
```
[Module H] 完成
- README.md: 重写为轻量版
- start.bat: 创建完成
- start.sh: 创建完成
- 验证: 3 个文件就绪 ✓
```

---

## 11. 集成验证 (所有 Module 完成后执行)

当全部 8 个 Module 完成报告后，按顺序执行以下验证:

### Step 1: 残留检查

```bash
cd D:\桌面\test\prophetic-dream-fund\backend
# 搜索 Redis 残留引用 (应该无结果)
grep -rn "from redis.asyncio" app/
grep -rn "get_redis" app/
grep -rn "import redis" app/
```

### Step 2: 安装新依赖

```bash
cd D:\桌面\test\prophetic-dream-fund\backend
pip install -r requirements.txt
```

### Step 3: 验证 Python 导入

```bash
cd D:\桌面\test\prophetic-dream-fund\backend
python -c "from app.main import app; print('✓ Backend imports OK')"
```

如果报错:
- `ImportError: No module named 'redis'` → 检查残留引用
- `ImportError: No module named 'app.redis_client'` → 检查 main.py 或 jobs.py 残留
- `ImportError: No module named 'apscheduler'` → 检查 main.py 残留

### Step 4: 初始化数据库

```bash
cd D:\桌面\test\prophetic-dream-fund\backend
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
# 应输出: Database tables created/verified
```

### Step 5: 启动后端

```bash
cd D:\桌面\test\prophetic-dream-fund\backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 应看到: Uvicorn running on http://127.0.0.1:8000
```

### Step 6: 启动前端

在另一个终端:
```bash
cd D:\桌面\test\prophetic-dream-fund\frontend
npx vite --host 127.0.0.1 --port 5173
```

### Step 7: 功能验证

浏览器访问 `http://localhost:5173`:
1. 页面正常加载（无白屏 / 无 JS 报错）
2. 仪表盘页面正常显示
3. 基金搜索能输入关键字（可能需要先触发 `POST /api/v1/data/trigger-refresh` 拉取数据）
4. 持仓管理页面正常
5. 推荐页面正常

### Step 8: 最终检查清单

- [ ] `docker-compose.yml` 已删除
- [ ] `nginx.conf` 已删除
- [ ] 所有 `Dockerfile` 和 `.dockerignore` 已删除
- [ ] `backend/app/redis_client.py` 已删除
- [ ] `backend/app/config.py` 无 `REDIS_URL`
- [ ] `backend/app/database.py` 使用 SQLite + aiosqlite
- [ ] `backend/app/main.py` lifespan 无 Redis/Scheduler
- [ ] `backend/app/api/dependencies.py` 无 `get_redis`
- [ ] `backend/app/services/cache_service.py` 为内存缓存实现
- [ ] 3 个 Service 文件构造函数无 `redis` 参数
- [ ] 6 个 API 路由文件无 `redis: Redis = Depends(get_redis)`
- [ ] `backend/app/scheduler/jobs.py` 使用 `get_cache()`
- [ ] `backend/requirements.txt` 无 asyncpg/alembic/redis/apscheduler
- [ ] `backend/.env` 已最小化
- [ ] `README.md` 已重写
- [ ] `start.bat` + `start.sh` 已创建
- [ ] `backend/app` 中 `grep -r "redis.asyncio"` 无结果
- [ ] `backend/app` 中 `grep -r "get_redis"` 无结果
- [ ] `pip install -r requirements.txt` 成功
- [ ] `python -c "from app.main import app"` 成功
- [ ] `init_db()` 执行成功
- [ ] `uvicorn app.main:app` 启动成功
- [ ] 前端 `http://localhost:5173` 可访问

---

## 附录: 调度命令参考

如果你使用支持 Workflow 的 AI 工具，可以一次性派发全部 8 个 Module:

```
对 8 个子 Agent 并行派发以下任务:
- Agent 1: 执行 Module A (清理)
- Agent 2: 执行 Module B (基础设施)
- Agent 3: 执行 Module C (缓存层)
- Agent 4: 执行 Module D (入口)
- Agent 5: 执行 Module E (服务层)
- Agent 6: 执行 Module F (调度器)
- Agent 7: 执行 Module G (API层)
- Agent 8: 执行 Module H (文档脚本)

全部完成后，执行集成验证。
```

或者分两波:
```
Wave 1 (并行): Module A, B, C, H
↓ 全部完成
Wave 2 (并行): Module D, E, F, G
↓ 全部完成
集成验证
```
