# Data Analyst Agent

面向多业务、多表场景的智能数据分析工作台原型。项目目标是把自然语言问数转化为可解释、可复盘的数据分析任务，覆盖 Schema 理解、表关联推理、SQL 生成、错误自修复、结果预览、图表洞察和多轮追问。

## 快速入口

- [文档总览](docs/README.md)
- [项目介绍](docs/product/project-introduction.md)
- [Web UI 技术规范](docs/frontend/web-ui-spec.md)
- [后端架构说明](docs/backend/architecture.md)

## 目录结构

```text
.
├── agent/                  # Agent 核心模块
├── docs/                   # 产品、前端、后端和归档文档
├── scripts/                # 数据、文档和架构图生成脚本
├── src/                    # Next.js 前端源码
├── tests/                  # 前端测试
├── backend_app.py          # FastAPI 后端入口
├── package.json            # 前端依赖和脚本
├── requirements.txt        # Python 依赖
└── docker-compose.mysql.yml
```

## 常用命令

```bash
npm install
npm run dev
npm test
npm run test:e2e
```

后端和 Docker MySQL demo 的启动方式见 [项目介绍](docs/product/project-introduction.md)。
