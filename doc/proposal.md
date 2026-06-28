# 预知梦基金 — 轻量化重构提案 (Lightweight Refactor Proposal)

> **目标**: 将项目从 "Docker 多服务架构" 简化为 "单用户本地即时启动" 的个人工具，参考 `fund-recommend_refe` 的极简哲学，同时保留预知梦基金已有的核心功能优势。

---

## 一、现状分析

### 1.1 当前架构 (prophetic-dream-fund)

```
┌──────────────────────────────────────────────────┐
│  Docker Compose (5 个容器)                        │
│                                                   │
│  nginx:alpine ──→ frontend (React SPA)            │
│       │                                           │
│       └────────→ backend (FastAPI + uvicorn)       │
│                     │          │                  │
│              postgres:15    redis:7               │
│              (数据库)       (缓存)                 │
└──────────────────────────────────────────────────┘
```

| 指标 | 数值 |
|------|------|
| 容器数量 | 5 (nginx + frontend + backend + postgres + redis) |
| 后端代码文件 | ~35 个 Python 文件 |
| 前端代码文件 | ~30 个 TypeScript 文件 |
| 数据库表 | 10 张 |
| 后端依赖 | fastapi, sqlalchemy, asyncpg, alembic, redis, apscheduler, pandas, numpy, httpx, paddleocr 等 |
| 前端依赖 | react, react-router, antd, echarts, zustand, axios, dayjs, vite 等 |
| 冷启动时间 | `docker compose up -d` → 镜像构建 + 容器启动 (数分钟) |
| 资源占用 | 5 个容器常驻内存 (~500MB+) |

### 1.2 参考项目 (fund-recommend_refe)

```
┌──────────────────────────────────────────────┐
│  Node.js Express (单一进程, 319 行)           │
│       │                                       │
│       ├── public/index.html  (97 行)          │
│       ├── public/app.js      (1346 行)        │
│       └── public/styles.css  (410 行)         │
│                                               │
│  外部 API ←── 天天基金 / 东方财富              │
└──────────────────────────────────────────────┘
```

| 指标 | 数值 |
|------|------|
| 进程数量 | 1 |
| 源代码文件 | 4 个 |
| 数据库 | 无 (localStorage + 实时抓取) |
| 缓存 | 无 |
| 依赖数量 | 4 个 npm 包 (express, axios, cors, iconv-lite) |
| 构建步骤 | 零 (纯 JS, 无需编译) |
| 冷启动时间 | `node server.js` → < 1 秒 |
| 资源占用 | 单进程 ~50MB |

### 1.3 差距诊断

预知梦基金的核心问题不是 "功能太多"，而是 **架构为多用户/生产环境设计，个人使用严重过度工程化**:

| 组件 | 当前用途 | 个人使用是否必要 |
|------|----------|:---:|
| Docker Compose | 编排 5 个服务 | ❌ 完全不需要 |
| Nginx 反向代理 | 路由前后端 + 静态文件缓存 | ❌ Vite proxy 已够用 |
| PostgreSQL | 持久化基金数据、用户持仓 | ❌ SQLite 完全够用 |
| Redis | 缓存 NAV、基金列表 | ❌ 内存字典 / SQLite 即可 |
| APScheduler | 定时拉取市场数据 | ⚠️ 可改为按需拉取 |
| Alembic | 数据库迁移 | ⚠️ SQLite 直接建表即可 |
| 多数据源适配器 | 4 个数据源 + 交叉验证 | ⚠️ 保留 1-2 个主力源即可 |
| PaddleOCR | 截图识别持仓 | ⚠️ 可选保留，按需安装 |

---

## 二、重构目标

### 2.1 核心原则

1. **零 Docker** — 删除所有 Dockerfile、docker-compose.yml、nginx.conf，不再使用容器
2. **零外部数据库依赖** — SQLite 替代 PostgreSQL + Redis，数据文件随项目存储
3. **一键启动** — 等同于 `start.bat`，从点击到可用 < 5 秒
4. **保持功能完整性** — 持仓管理、基金查询、智能推荐、回测分析、仪表盘全部保留
5. **个人使用优先** — 去掉多用户考量（user_id 外键保留但暂不启用）、去掉生产级部署考量

### 2.2 目标架构

```
┌──────────────────────────────────────────────┐
│  start.bat / start.sh  (一键启动)             │
│       │                                       │
│       ├──→ backend (FastAPI + uvicorn)        │
│       │       │                               │
│       │       └── fund_app.db (SQLite)        │
│       │                                       │
│       └──→ frontend (Vite dev server)         │
│               │                               │
│               └── proxy /api → localhost:8000  │
│                                               │
│  外部 API ←── 天天基金 / 东方财富              │
└──────────────────────────────────────────────┘
```

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 进程数 | 5 容器 | 2 进程 (uvicorn + vite) |
| 数据库 | PostgreSQL + Redis | SQLite (单文件) |
| 启动方式 | `docker compose up -d` | 双击 `start.bat` |
| 冷启动时间 | 数分钟 | < 5 秒 |
| 首次启动步骤 | 安装 Docker → 构建镜像 → 启动容器 | `pip install` + `npm install` → 运行 |
| 资源占用 | ~500MB+ | ~150MB |
| 代码文件数 | ~65 个 | ~40 个 (删除 Docker/nginx/Redis 相关) |

---

## 三、具体改造计划

### 3.1 删除清单

```
prophetic-dream-fund/
├── ✕ docker-compose.yml          # 不再需要
├── ✕ nginx.conf                   # 不再需要
├── ✕ backend/Dockerfile           # 不再需要
├── ✕ backend/.dockerignore        # 不再需要
├── ✕ frontend/Dockerfile          # 不再需要
├── ✕ frontend/.dockerignore       # 不再需要
├── ✕ frontend/nginx.conf          # 不再需要
└── ✕ backend/app/redis_client.py  # 不再需要
```

### 3.2 改造清单

#### 3.2.1 数据库层 — PostgreSQL → SQLite

**文件**: `backend/app/database.py`

- 替换 `asyncpg` 驱动为 `aiosqlite`
- 数据库 URL 固定为 `sqlite+aiosqlite:///./fund_app.db`
- 移除 `pool_size`、`max_overflow` 等连接池参数 (SQLite 不需要)
- 移除 Alembic 迁移 (SQLite 直接用 `Base.metadata.create_all` 建表)

**文件**: `backend/app/config.py`

- 删除 `REDIS_URL` 配置项
- 简化 `DATABASE_URL`，默认值改为 SQLite
- 删除 Docker 相关环境变量

**文件**: `backend/.env`

- 只保留最小配置，不再需要数据库连接字符串

#### 3.2.2 缓存层 — Redis → 内存字典

**文件**: 新建 `backend/app/cache.py` (替代 `redis_client.py`)

- 用 `dict` + 时间戳实现简单的 TTL 内存缓存
- 线程安全 (FastAPI 单线程异步不需要锁，但加上 `asyncio.Lock` 更安全)
- 支持的 key: `latest_nav:{code}`, `nav_30d:{code}`, `fund_list`, `hot_top20`

**涉及文件**:
- `backend/app/services/cache_service.py` — 将对 Redis 的操作改为对内存字典的操作
- `backend/app/services/fund_service.py` — 缓存查询适配
- `backend/app/api/dependencies.py` — 移除 `get_redis` 依赖注入

#### 3.2.3 数据调度 — APScheduler → 按需拉取

**文件**: `backend/app/scheduler/` — 整个重构

**新方案**:
- API 请求时检查本地 SQLite 数据新鲜度
- 如果数据过期 (> 1小时) 且缓存未命中，实时从外部 API 拉取
- 不再后台定时执行，改为 lazy-fetch 模式
- 保留手动触发刷新的 API (`POST /api/v1/data/trigger-refresh`)

**收益**:
- 移除 `apscheduler` 依赖
- 应用不跑定时任务，更省资源
- 用户打开页面时才更新数据，行为更可预测

#### 3.2.4 数据源适配器 — 精简

**文件**: `backend/app/adapters/`

**当前 4 个适配器**:
| 适配器 | 依赖 | 建议 |
|--------|------|------|
| `eastmoney.py` | httpx (已有) | ✅ 保留为主力 |
| `tiantian.py` | httpx (已有) | ✅ 保留为辅助 |
| `akshare.py` | akshare (可选) | ⚠️ 保留但默认不启用 |
| `tushare.py` | tushare (需 token) | ❌ 删除 (个人用户无 token) |

**简化 normalizer.py 和 cross_validator.py**:
- 2 个源做交叉验证即可 (原来为 4 个源设计)

#### 3.2.5 前端 — 保持 React + Vite

**决策**: 前端框架不改为 Vanilla JS。

**理由**:
- Vite dev server 启动 < 1 秒，不是瓶颈
- React + Ant Design + ECharts 提供的 UI 质量远超 Vanilla JS 重写
- 参考项目只有 1 个页面 + 3 个 Tab，预知梦基金有 6 个页面 + 复杂交互 (图表、表单、OCR 上传)
- 瓶颈在 Docker，不在 Vite

**优化措施**:
- 移除 `frontend/nginx.conf`、`frontend/Dockerfile`、`frontend/.dockerignore`
- `vite.config.ts` 的 proxy 配置已正确指向 `localhost:8000`，无需改动

#### 3.2.6 启动脚本

**新建**: `start.bat` (Windows) 和 `start.sh` (Linux/macOS)

```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   预知梦基金 (Prophetic Dream Fund)
echo   正在启动...
echo ========================================

:: 检查依赖
where python >nul 2>nul || (echo [错误] 请先安装 Python 3.11+ && pause && exit /b 1)
where node >nul 2>nul || (echo [错误] 请先安装 Node.js 18+ && pause && exit /b 1)

:: 后端首次初始化
if not exist "backend\fund_app.db" (
    echo [初始化] 首次运行，正在创建数据库...
    cd backend
    pip install -r requirements.txt >nul 2>nul
    python -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"
    cd ..
)

:: 前端首次初始化
if not exist "frontend\node_modules" (
    echo [初始化] 正在安装前端依赖...
    cd frontend
    npm install >nul 2>nul
    cd ..
)

:: 启动后端 (后台)
echo [启动] 后端服务 (port 8000)...
start "PropheticDreamFund-Backend" cmd /c "cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: 等待后端就绪
timeout /t 2 /nobreak >nul

:: 启动前端 (前台)
echo [启动] 前端服务 (port 5173)...
cd frontend
npx vite --host 127.0.0.1 --port 5173

pause
```

**也可以考虑更简单的方案** — 后端 FastAPI 直接 serve 前端构建产物:
- `vite build` → 生成 `frontend/dist/`
- FastAPI 挂载静态文件 + SPA fallback
- 只需要启动一个 uvicorn 进程
- 这就是参考项目的模式 (Express serve public/)

### 3.3 分阶段执行

#### Phase 1: 去 Docker 化 (立即)

| 任务 | 描述 |
|------|------|
| 1.1 | 删除所有 Docker 相关文件 |
| 1.2 | 数据库改为 SQLite (`database.py` + `config.py`) |
| 1.3 | 移除 `redis_client.py` 和 Redis 依赖注入 |
| 1.4 | 内存缓存替代 Redis (`cache_service.py`) |
| 1.5 | 创建 `start.bat` / `start.sh` 启动脚本 |
| 1.6 | 更新 `README.md` |

**验收标准**: 执行 `start.bat` 后，打开浏览器 `http://localhost:5173` 可正常使用全部功能。

#### Phase 2: 简化架构 (本周)

| 任务 | 描述 |
|------|------|
| 2.1 | APScheduler 改为按需拉取 (lazy-fetch) |
| 2.2 | 删除 Tushare 适配器 |
| 2.3 | 简化 `normalizer.py` / `cross_validator.py` |
| 2.4 | 删除 Alembic，用 `Base.metadata.create_all` |
| 2.5 | 清理 `requirements.txt` (移除 apscheduler, asyncpg, alembic, redis) |

**验收标准**: 后端依赖数量减少 40%+，启动内存占用下降 30%+。

#### Phase 3: 体验优化 (可选)

| 任务 | 描述 |
|------|------|
| 3.1 | 后端单进程 serve 前后端 (FastAPI 挂载静态文件) |
| 3.2 | 首次加载骨架屏优化 |
| 3.3 | API 响应时间优化 (减少不必要的 DB 查询) |
| 3.4 | `pip install` 改为 `uv` 或 `pipx` 加速依赖安装 |

---

## 四、不做的事 (明确范围边界)

以下功能**不在本次重构范围**内:

- ❌ 多用户支持 (user_id 字段保留但不启用)
- ❌ 移动端 / PWA 适配
- ❌ CI/CD 流水线
- ❌ 生产环境部署指南
- ❌ Kubernetes / 云部署
- ❌ 数据加密 / 登录认证
- ❌ 前端框架从 React 改为 Vanilla JS (不值得，React 生态提供了更好的可维护性)
- ❌ 微服务拆分

---

## 五、对比总结

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| **理念** | 为生产环境设计的微服务 | 为个人使用设计的单体应用 |
| **容器化** | Docker Compose (5 容器) | 无 |
| **数据库** | PostgreSQL + Redis | SQLite |
| **启动方式** | `docker compose up -d` | 双击 `start.bat` |
| **启动耗时** | 首次数分钟 | 首次 < 30秒，后续 < 5秒 |
| **运行占用** | ~500MB | ~150MB |
| **依赖数量** | ~40 (Python) + ~500 (Node) | ~15 (Python) + 同前 (Node) |
| **代码文件** | ~65 | ~40 |
| **核心功能** | 持仓/查询/推荐/回测/OCR/仪表盘 | 完全相同 + 更快响应 |

---

## 六、与参考项目对标

`fund-recommend_refe` 证明了基金工具的**正确尺寸**: 单一进程、零数据库、按需拉取外部数据、HTML+JS+CSS 三文件即可完成核心功能。

预知梦基金的差异化价值在于:
1. **持仓管理** — 参考项目只有自选列表，没有持仓 P&L 计算
2. **智能推荐引擎** — 多因子打分、风险匹配、组合优化、回测
3. **数据持久化** — 本地 SQLite 保存历史数据，离线可查
4. **UI 体验** — React + Ant Design 提供专业级交互

这些功能需要一定的基础设施 (数据库 + 后端)，但**不需要 Docker + PostgreSQL + Redis 的重量**。本次重构的核心就是找到这个平衡点 — 用最轻的方式承载最完整的个人投研功能。

---

*提案日期: 2026-06-28*
*作者: 预知梦基金项目组*
