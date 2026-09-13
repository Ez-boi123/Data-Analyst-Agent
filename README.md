# Data Analyst Agent

用自然语言提问，查看 SQL、图表、分析结论和执行证据。

Data Analyst Agent 是一个面向本地演示与原型验证的数据分析工作台。它读取数据源的表结构与字段画像，生成并执行 SQL，在查询报错时尝试修复，再输出图表建议和中文分析。你可以在同一个任务中继续追问，逐步细化分析范围。

![任务首页：输入分析问题并查看历史任务](docs/assets/screenshots/task-home.png)

> 本文截图来自内置「华东区 GMV 下滑归因」演示任务，用于说明界面布局。截图中的数据、SQL、步骤、置信度及分支数量都是示例，不代表你连接的数据源或本次分析结果。真实任务以运行时返回的内容为准。

## 开始之前

| 项目 | 要求 |
| --- | --- |
| Node.js 与 npm | Node.js 20.9 或以上；npm 随 Node.js 安装 |
| Python | 建议 Python 3.11 或以上，能够使用 `venv`、`sqlite3` 和 `pip` |
| 模型接口 | 支持 OpenAI 兼容 Chat Completions 的服务地址、API Key 和模型 ID |
| 数据 | 可先用仓库里的 `淘宝用户行为.csv`，也可配置数据库连接 |
| Docker | 仅在使用下文 MySQL 多表演示时需要 |

所有命令均在项目根目录执行。下面主要使用 Windows PowerShell；如果系统拦截 `npm.ps1`，将命令中的 `npm` 改成 `npm.cmd`。

## 快速启动：先用内置 CSV 完成一次分析

### 1. 安装依赖

下载或克隆项目后，进入包含 `package.json` 的目录，执行：

```powershell
npm run setup
```

该命令安装前端依赖，并在项目内创建或复用 `.venv`，安装 Python 后端依赖，无需手动激活虚拟环境。

### 2. 配置模型和数据源

第一次配置时，将 `.env.example` 复制为 `.env`。已有 `.env` 时直接编辑，保留现有配置。

```powershell
Copy-Item .env.example .env
```

填写以下配置，尖括号内容需替换为自己的值：

```dotenv
LLM_BASE_URL=<服务商提供的 OpenAI 兼容 API 根地址>
LLM_API_KEY=<你的 API Key>
LLM_MODEL=<该服务可用的模型 ID>

# 首次体验使用仓库自带 CSV，不连接 MySQL
DATA_SOURCE_URL=
DEMO_DATABASE_URL=
```

注意 `.env.example` 默认包含 MySQL 演示连接。**如果尚未启动 MySQL，请清空 `DEMO_DATABASE_URL`**，否则程序会尝试连接数据库，而不会读取 CSV。

未配置数据库地址时，后端读取项目根目录的 `淘宝用户行为.csv`，注册为 `sample_orders` 表。请保留此文件。模型配置写在 `.env` 中，不在网页“设置”页填写；`.env` 已加入 Git 忽略列表，请勿提交 API Key。

### 3. 同时启动前后端

```powershell
npm run dev:all
```

看到前端 `Ready` 和后端 `Application startup complete` 后，打开终端显示的前端地址：

- 前端默认：[http://localhost:3000](http://localhost:3000)。端口占用时可能变为 3001、3003 等，以终端的 `Local` 地址为准。
- 后端健康检查：[http://127.0.0.1:8001/api/health](http://127.0.0.1:8001/api/health)。`ok: true` 表示后端响应，`configured: true` 表示模型配置项和依赖可用；它不会验证 API Key 是否能实际调用模型。
- API 文档：[http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)。

保持终端运行，结束时按 `Ctrl+C`。只执行 `npm run dev` 会启动前端，无法独立完成真实分析。

### 4. 提交第一个问题

在首页输入框中输入：

> 按商品品类统计记录数和商品数量合计，按数量从高到低排序。

点击右侧发送按钮。系统创建任务并进入工作台，随后展示执行步骤、查询结果和分析文字。先用这种与现有字段直接对应的问题验证链路，再尝试复杂分析。

## 如何使用工作台

### 提问时写清楚范围和口径

尽量包含“分析对象 + 时间范围 + 分组维度 + 指标”。以下问题可用于默认 CSV：

```text
按性别统计购买记录数和平均年龄。
按商品品类统计商品数量合计，列出前 5 名。
统计各支付方式的记录数和占比。
```

日期分析请按数据实际日期提问；历史样例不一定包含“最近 7 天”的记录。涉及销售额时，请先明确 `price` 是单价还是整笔金额，避免错误口径。

输入框下方的“深度分析模型 / 快速 SQL 模型 / Schema 推理模型”目前是界面选项，尚未接入独立模型路由；实际使用的模型由 `.env` 的 `LLM_MODEL` 决定。

### 查看执行过程

进入任务后，左侧为 Agent 对话，右侧为证据时间线。点击时间线卡片可以查看该阶段的详情。

![分析工作台：Agent 对话、任务指标与证据时间线](docs/assets/screenshots/evidence-timeline.png)

真实分析通常依次经过 Schema 理解、表关联推理、SQL 生成、SQL 执行、图表建议和分析结论生成。SQL 报错时才会进入自修复，最多修复两次，总共最多执行三次。内置示例还包含产品流程展示卡片，实际步骤可能不同。

卡片状态分为“等待执行”“运行中”“完成”和“可恢复”。某个阶段完成不等于整个任务完成；以顶部任务状态和最终结果为准。

| 顶部指标 | 如何理解 |
| --- | --- |
| Schema 置信度 | 按字段完整性、样例覆盖、关联键质量和多表连通程度计算，显示为百分比。它是结构质量规则评估，不是答案正确概率；无可评估数据时显示“未评估”。 |
| SQL 自修复 | 本任务累计开始的修复次数，随执行步骤更新；同一次修复完成时不重复计数。 |
| 追问与分支 | 普通追问次数与子任务分支数量分别统计。在原任务聊天框追问不会自动创建子任务。 |

评分公式与扣分原因可在“Schema”详情查看，也可阅读 [Schema 评估说明](docs/backend/schema-confidence.md)。

### 阅读图表和结果

选择“洞察”标签查看图表、关键发现和下一步建议；下方结果预览用于核对模型结论是否有数据支持。

![洞察与结果：趋势图、关键证据、可能原因和结果表](docs/assets/screenshots/insights-results.png)

不同任务的结果字段和图表类型会不同。模型输出的“可能原因”应作为待验证假设，不能直接当成因果结论。当前分析文字基于有限行数的查询结果预览生成。

当前结果表默认每页 5 行、最多展示 12 列，尚未提供完整翻页控件；“导出 CSV”按钮尚未接入下载逻辑，不能用它导出完整结果。

### 检查 SQL 与修复记录

点击对应的 SQL 生成、执行或自修复卡片，再切换到“SQL”标签，查看查询文本、执行状态、报错与重试历史。

![SQL 详情：查询文本、执行说明和修复记录](docs/assets/screenshots/sql-details.png)

建议重点检查：选表是否合理、日期范围是否正确、关联是否造成重复计数、聚合指标是否符合业务口径。SQL 能执行成功，并不代表业务计算一定正确。

真实执行使用 SQLite 方言，即使原始数据来自 MySQL。截图中的 SQL 为演示文本，不应直接复制到真实数据源执行。

### 继续追问与分享

在左侧底部输入追问，例如：

```text
只看女性用户，再按商品品类分组。
把刚才的结果按数量降序排列，只保留前三名。
```

系统结合上一轮的问题、SQL 和结论补全追问，再执行新一轮分析。要切换到完全不同的分析主题，可以返回首页新建任务。

右上角“分享任务”可打开任务展示页。当前分享页用于本地展示，评论和创建分支等交互尚未完整接通；也没有正式的登录、成员授权或访问控制。后端支持通过创建任务 API 的 `parentTaskId` 建立子任务关系。

## 使用自己的数据库或 MySQL 多表示例

### 连接已有数据库

在 `.env` 中设置 SQLAlchemy 连接 URL，例如：

```dotenv
DATA_SOURCE_URL=mysql+pymysql://<用户名>:<密码>@<主机>:<端口>/<数据库名>
```

数据库密码包含特殊字符时，需要按 URL 规则编码。其他数据库类型需要相应的 SQLAlchemy 驱动。网页“数据源 / Schema”目前用于查看数据源信息，新增连接通过配置文件完成。

默认数据源地址的读取顺序为 `DATA_SOURCE_URL` → `DEMO_DATABASE_URL` → 内置 CSV。创建任务 API 还允许用 `dataSourceUrl` 覆盖本任务的数据源。

后端会将数据库中的表和视图读取到内存，再注册为 SQLite 查询表；适合先连接规模可控的演示数据，并使用只读数据库账号。数据源画像有进程内缓存，修改数据或配置后需要重启后端重新加载。

### 启动 MySQL 演示库（可选）

先完成 `npm run setup`，再启动 Docker：

```powershell
docker compose -f docker-compose.mysql.yml up -d
docker compose -f docker-compose.mysql.yml ps
```

等待 MySQL 状态变为 `healthy`，首次初始化数据：

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap_mysql_demo.py
```

macOS / Linux 对应命令为 `.venv/bin/python scripts/bootstrap_mysql_demo.py`。脚本使用本地演示连接，将原始 CSV 转换并扩展为用户、商品、订单、曝光和点击五张表。部分维度和行为数据为合成演示数据。

已有同名表时脚本不会默认覆盖；只有需要重新生成演示库时才使用 `--replace`，它会替换演示表及数据。

然后在 `.env` 中设置：

```dotenv
DATA_SOURCE_URL=
DEMO_DATABASE_URL=mysql+pymysql://agent:agent_demo_123@127.0.0.1:3307/data_agent_demo
```

重启应用后，可以提问：

> 按年龄段和性别统计订单数、销售额和客单价，销售额按 order_amount 求和。

> 按品类统计曝光次数、点击次数和订单数。

这套示例没有退款字段，也不包含用户具体城市；城市层级不等于具体城市。截图中的华东区和退款分析来自另一套静态演示任务。

## 常见问题

| 现象 | 处理方法 |
| --- | --- |
| `Failed to fetch` | 检查后端健康地址是否能打开，确认前后端都在运行。默认 API 地址是 `http://127.0.0.1:8001`；若后端改了地址，可设置 `NEXT_PUBLIC_API_BASE_URL` 后重启前端。 |
| `WinError 10048`，8001 端口占用 | 通常是已有后端仍在运行。回到旧终端按 `Ctrl+C` 停止旧实例，再启动 `npm run dev:all`，不要重复启动后端。 |
| 启动后前端也退出 | `dev:all` 中任一服务退出会停止其他服务，先查看最早出现的后端或前端错误。 |
| 提交后总是看到“华东区 GMV 下滑归因” | 创建任务失败时会跳到离线示例；URL 含 `offline=1` 或任务 ID 为 `task-gmv-east-7d` 表示示例任务。先修复后端连接，再从首页重新提交。 |
| 模型未配置、鉴权失败或模型不可用 | 检查 `.env` 的 API 根地址、Key、模型 ID 和服务额度；修改后重启后端。 |
| MySQL 连接失败 | 使用 CSV 时清空数据库 URL；使用 Docker 演示时确认容器健康、端口为 3307，并已初始化数据。 |
| Python 缺少依赖或后端环境不可用 | 运行 `npm run setup:backend`；若未找到 Python，先安装包含 `venv` 和 `sqlite3` 的 Python 环境。 |
| 提示缺少字段、返回 `schema_notice` 或结果为空 | 查看 Schema，确认问题所需字段和日期范围确实存在；不要将截图中的字段名套用到自己的数据。 |
| 重启后任务找不到，或打开旧链接出现示例 | 当前任务保存在后端内存中，重启后清空；任务读取失败时页面可能回退到示例。请重新创建任务。 |

## 当前使用边界

- 项目是原型工作台。数据源连接、模型配置通过环境变量管理，网页尚未提供完整管理功能。
- 查询前会限制语句类型并阻止写入类关键词；SQL 未带 `LIMIT` 时默认追加 500。界面里的“超时 30s”“字段脱敏”“业务域权限过滤”等标签不代表已经实现对应的完整安全机制。
- 模型服务会收到字段画像、样例值和部分查询结果。请确认所用数据允许发送给配置的模型服务。
- 历史任务、对话和结果尚未持久化；分享页不是独立保存的报告，也不能恢复重启前的任务。

## 开发命令与文档

| 命令 | 用途 |
| --- | --- |
| `npm run setup` | 安装前后端依赖 |
| `npm run dev:all` | 同时启动前后端 |
| `npm run dev` | 仅启动 Next.js 前端 |
| `npm run dev:backend` | 仅启动 FastAPI 后端 |
| `npm run setup:backend` | 安装或补齐 Python 依赖 |
| `npm test` | 前端单元测试 |
| `npm run test:e2e` | Playwright 端到端测试，首次需要安装对应浏览器 |
| `npm run build` | 构建前端 |

```text
agent/              Schema 画像、SQL 生成、自修复与图表逻辑
src/                Next.js 页面与工作台组件
backend_app.py      FastAPI 后端、任务状态与流式事件
scripts/            环境安装、启动与演示数据初始化
tests/              回归测试
docs/               设计文档、技术说明和截图
```

- [文档总览](docs/README.md)
- [项目介绍](docs/product/project-introduction.md)
- [后端架构说明](docs/backend/architecture.md)
- [Schema 置信度评估](docs/backend/schema-confidence.md)
- [Web UI 技术规范](docs/frontend/web-ui-spec.md)
