# Data Analyst Agent

面向多业务、多表场景的智能数据分析 Agent Demo。项目支持接入业务数据库，自动完成 Schema 理解、表关联推理、SQL 生成、SQL 执行、自修复、图表建议和深度分析，目标是把自然语言问数转化为可解释、可复盘的数据分析任务。

## 核心能力

- **Schema 理解**：自动读取表结构，生成字段类型、样例值、缺失率、唯一值数量和业务含义猜测。
- **表关联推理**：识别 `customer_id`、`product_id`、`order_id`、`exposure_id` 等候选 Join Path。
- **SQL Agent**：基于 LangChain 和 OpenAI-compatible API 生成只读 SQL，并进行安全校验和自动限行。
- **错误自修复**：SQL 执行失败后，结合原 SQL、错误信息和 Schema 自动修复并重试。
- **深度分析**：基于查询结果生成图表建议、关键发现、可能原因和下一步分析建议。
- **多轮追问**：保留上一轮问题、SQL 和分析结论，支持同一任务内继续问数。

## 技术栈

- 后端：FastAPI、LangChain、pandas、SQLAlchemy、SQLite runtime
- 前端：Next.js、React、TypeScript、TanStack Table、ECharts、React Flow
- 数据库：Docker MySQL 8.0
- 模型：OpenAI-compatible Chat Completions API

## 目录结构

```text
.
├── agent/                         # Agent 核心模块
├── src/                           # Next.js 前端源码
├── tests/                         # 前端测试
├── scripts/                       # MySQL 造数、文档和架构图生成脚本
├── docs/                          # 项目介绍、架构图、PDF 文档
├── backend_app.py                 # FastAPI 后端入口
├── package.json                   # 前端依赖和脚本
├── docker-compose.mysql.yml       # Docker MySQL demo 数据库
├── requirements.txt               # Python 依赖
└── 淘宝用户行为.csv                # 默认 demo 原始订单数据
```

## 快速启动

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入模型 API Key。

```bash
cp .env.example .env
```

关键配置：

```text
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=openai/gpt-5.4
DEMO_DATABASE_URL=mysql+pymysql://agent:agent_demo_123@127.0.0.1:3307/data_agent_demo
```

### 3. 启动 MySQL demo 数据库

```bash
docker compose -f docker-compose.mysql.yml up -d
python scripts/bootstrap_mysql_demo.py --replace
```

### 4. 启动后端

```bash
python -m uvicorn backend_app:app --host 127.0.0.1 --port 8001
```

### 5. 启动前端

```bash
npm install
npm run dev
```

前端默认连接后端：

```text
http://127.0.0.1:8001
```

## Demo 问题

- 按年龄段和性别统计订单数、销售额、客单价
- 不同年龄和性别用户从曝光到点击再到购买的转化率是多少
- 年轻女性最偏好的商品品类是什么，和男性相比有什么差异
- 哪些品类高曝光高点击但购买转化低
- 按性别和年龄段分析支付方式偏好，并给出业务建议

## 文档

- [项目介绍](docs/project_introduction.md)
- [项目介绍 PDF](docs/project_introduction.pdf)
- [后端架构说明](docs/backend_architecture.md)
- [新版后端架构图](docs/data_agent_backend_architecture_v2.svg)
