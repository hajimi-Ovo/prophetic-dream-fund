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
