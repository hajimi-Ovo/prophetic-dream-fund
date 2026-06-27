# 预知梦基金 (Prophetic Dream Fund)

面向个人投资者的基金交互平台 — 提供基金数据查询、OCR 识别、回测分析等一站式投研工具。

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| **后端** | Python 3.11+ / FastAPI / SQLAlchemy (async) / Celery |
| **前端** | TypeScript / Vue 3 / Vite |
| **数据库** | PostgreSQL 15 |
| **缓存/队列** | Redis 7 |
| **反向代理** | Nginx (Alpine) |
| **容器化** | Docker + Docker Compose v2 |

## 快速开始（Docker）

确保已安装 [Docker](https://www.docker.com/) 和 Docker Compose v2，然后执行：

```bash
# 克隆项目
git clone <your-repo-url>
cd prophetic-dream-fund

# 启动所有服务
docker compose up -d

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f
```

服务启动后访问 `http://localhost` 即可使用。

## 本地开发（不使用 Docker）

### 前置依赖

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量（根据实际情况修改）
cp ../.env.example .env

# 数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API 文档访问 `http://localhost:8000/docs`。

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

开发服务器默认运行在 `http://localhost:5173`，API 请求自动代理到后端。

## 项目结构

```
prophetic-dream-fund/
├── docker-compose.yml         # Docker 编排配置
├── nginx.conf                 # Nginx 反向代理配置
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略规则
├── README.md                  # 项目说明
├── backend/                   # 后端服务
│   ├── .dockerignore          # Docker 构建忽略
│   ├── .env                   # 本地环境变量
│   ├── Dockerfile             # 后端镜像
│   ├── requirements.txt       # Python 依赖
│   └── app/                   # 应用代码
│       ├── main.py            # FastAPI 入口
│       ├── api/               # API 路由
│       ├── models/            # 数据模型
│       ├── services/          # 业务逻辑
│       └── tasks/             # 异步任务 (Celery)
├── frontend/                  # 前端应用
│   ├── .dockerignore          # Docker 构建忽略
│   ├── Dockerfile             # 前端镜像
│   ├── package.json           # Node.js 依赖
│   └── src/                   # Vue 3 源码
│       ├── components/        # 通用组件
│       ├── views/             # 页面视图
│       ├── router/            # 路由配置
│       └── api/               # API 调用层
├── docs/                      # 项目文档
└── scripts/                   # 辅助脚本
```

## Docker 服务说明


| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| nginx | nginx:alpine | 80 | 反向代理，路由前端静态资源和后端 API |
| backend | 本地构建 | - | FastAPI 后端，处理业务逻辑 |
| frontend | 本地构建 | - | Vue 3 前端，由 Nginx 代理 |
| postgres | postgres:15-alpine | 5432 | 关系型数据库，持久化基金数据 |
| redis | redis:7-alpine | 6379 | 缓存与 Celery 消息队列 |

## 许可证

[MIT](LICENSE)
