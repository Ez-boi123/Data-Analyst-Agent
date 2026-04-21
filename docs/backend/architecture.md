# 数据分析 Agent 后端架构图

这份图面向比赛答辩和前后端联调，突出后端如何把前端任务、Schema 理解、表关联推理、SQL 生成、自修复、图表建议和深度分析串成完整 Agent 链路。

## 0. 展示版 SVG 架构图

已按 `fireworks-tech-graph` 的扁平技术图风格生成展示版 SVG：

- [agent-backend-architecture-fireworks.svg](../assets/agent-backend-architecture-fireworks.svg)

## 1. 后端总体架构

```mermaid
flowchart TB
    subgraph FE["前端分析工作台 / Next.js"]
        Chat["左侧 Agent 对话"]
        Workspace["右侧结构化分析区"]
        TaskView["任务、步骤、SQL、图表、洞察"]
    end

    subgraph API["FastAPI 后端 backend_app.py"]
        Health["GET /api/health"]
        SchemaAPI["GET /api/data-sources/default/schema"]
        TaskAPI["POST /api/tasks\nGET /api/tasks/{id}"]
        MessageAPI["POST /api/tasks/{id}/messages"]
        StreamAPI["GET /api/tasks/{id}/stream\nPOST /api/tasks/{id}/runs/stream"]
        TaskStore["内存任务状态\nTASKS / steps / messages / lastRun"]
        CatalogCache["数据目录缓存\nCATALOG_CACHE"]
    end

    subgraph Agent["LangChainDataAgent"]
        Rephrase["多轮追问改写"]
        SchemaTool["Schema 理解"]
        RelationTool["表关联推理"]
        SQLGen["SQL 生成"]
        SQLExec["只读 SQL 执行"]
        SQLRepair["SQL 自修复"]
        ChartTool["结构化图表建议"]
        Insight["流式深度分析"]
    end

    subgraph Data["数据源层"]
        CSV["默认 CSV 示例数据"]
        Upload["CSV / Excel 上传数据"]
        SQLite["SQLite 文件"]
        MySQL["Docker MySQL Demo\n5 张电商分析表"]
        MemorySQLite["运行时 SQLite 连接\n统一执行查询"]
    end

    subgraph LLM["OpenAI-compatible LLM"]
        Model["OpenAI / DeepSeek / 通义千问等\nLLM_BASE_URL + LLM_API_KEY + LLM_MODEL"]
    end

    Chat --> TaskAPI
    Chat --> MessageAPI
    Chat --> StreamAPI
    Workspace --> SchemaAPI
    StreamAPI --> TaskStore
    TaskAPI --> TaskStore
    MessageAPI --> TaskStore
    SchemaAPI --> CatalogCache
    StreamAPI --> CatalogCache

    CatalogCache --> CSV
    CatalogCache --> Upload
    CatalogCache --> SQLite
    CatalogCache --> MySQL
    CSV --> MemorySQLite
    Upload --> MemorySQLite
    SQLite --> MemorySQLite
    MySQL --> MemorySQLite

    StreamAPI --> Agent
    Agent --> Model
    SQLExec --> MemorySQLite

    Agent -->|SSE: step/token/result/done| StreamAPI
    StreamAPI --> Chat
    StreamAPI --> Workspace
    TaskStore --> TaskView
```

## 2. 一次问数请求时序

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端分析工作台
    participant API as FastAPI 后端
    participant DS as 数据源与 Schema 层
    participant AG as LangChainDataAgent
    participant DB as 只读查询连接
    participant LLM as OpenAI-compatible LLM

    U->>FE: 输入自然语言问题
    FE->>API: POST /api/tasks
    API-->>FE: 返回 taskId 和初始任务状态

    FE->>API: GET /api/tasks/{taskId}/stream
    API->>DS: 加载数据源并生成 Schema Profile
    DS-->>API: 表结构、字段画像、关联候选
    API-->>FE: SSE task: understanding

    API->>AG: stream(question, schema, connection, history)
    AG-->>FE: SSE step: Schema 理解
    AG-->>FE: SSE step: 表关联推理

    AG->>LLM: 基于问题、Schema、关联路径生成 SQL
    LLM-->>AG: 只读 SQL
    AG-->>FE: SSE step: SQL 生成完成

    AG->>AG: SQL 安全校验 SELECT / WITH
    AG->>DB: 执行加 LIMIT 的只读 SQL

    alt SQL 执行成功
        DB-->>AG: 查询结果 DataFrame
        AG-->>FE: SSE step: SQL 执行成功
    else SQL 执行失败
        DB-->>AG: 错误信息
        AG-->>FE: SSE step: SQL 执行失败
        AG->>LLM: 发送错误、原 SQL、Schema 请求修复
        LLM-->>AG: 修复后 SQL
        AG->>DB: 最多重试 2 次
    end

    AG->>LLM: 根据结果生成图表 JSON 建议
    LLM-->>AG: chart_type / x / y / size / color / reason
    AG-->>FE: SSE step: 图表建议

    AG->>LLM: 流式生成业务洞察
    loop token streaming
        LLM-->>AG: 分析 token
        AG-->>FE: SSE token
    end

    AG-->>API: AgentRun
    API->>API: 更新 task.lastRun / steps / messages
    API-->>FE: SSE result
    API-->>FE: SSE done
```

## 3. Agent 内部执行流水线

```mermaid
flowchart LR
    Q["用户问题 / 追问"] --> H{是否有历史轮次}
    H -->|是| R["问题改写\n补全指代与上下文"]
    H -->|否| S1["Schema 理解"]
    R --> S1

    S1 --> S2["表关联推理\ncustomer_id / product_id 等候选 Join Path"]
    S2 --> S3["SQL 生成\n只输出 SELECT / WITH"]
    S3 --> G["SQL 安全闸门\n禁止写操作 + 自动 LIMIT"]
    G --> E["执行 SQL"]

    E --> OK{执行成功?}
    OK -->|否| ERR["记录错误信息"]
    ERR --> FIX["SQL 自修复\nSchema + 原 SQL + 错误"]
    FIX --> G

    OK -->|是| C["图表建议\nbar / line / pie / scatter / bubble / table"]
    C --> I["深度分析\n趋势、异常、原因、建议"]
    I --> OUT["结构化 AgentRun\nSQL + 表格 + 图表配置 + 洞察"]
```

## 4. 后端模块职责

```mermaid
flowchart TB
    Backend["backend_app.py\n前端 API / SSE / 任务状态"] --> LC["agent/langchain_agent.py\nLangChain Agent 编排"]
    Backend --> DS["agent/data_source.py\nCSV / Excel / SQLite / SQLAlchemy URL"]
    Backend --> Schema["agent/schema.py\n字段画像 / 类型推断 / 关联候选"]
    Backend --> Chart["agent/charts.py\n结构化图表渲染建议适配"]

    LC --> SQL["agent/sql_agent.py\nSQL Prompt / 安全校验 / LIMIT / 结果模型"]
    LC --> LLM["langchain-openai ChatOpenAI\nOpenAI-compatible API"]
    DS --> RuntimeDB["运行时 SQLite 查询连接"]
    Schema --> Profile["SchemaProfile\nTableProfile / ColumnProfile / RelationCandidate"]
    Chart --> Plot["前端图表配置\nchartType / x / y / size / color / dataset"]
```

## 5. 推荐给前端的 SSE 事件

```mermaid
stateDiagram-v2
    [*] --> task
    task --> step
    step --> token: 深度分析流式输出
    step --> result: AgentRun 完成
    token --> token
    token --> result
    result --> done
    step --> error: 可恢复失败
    error --> [*]
    done --> [*]
```

事件含义：

- `task`：任务元信息和当前状态。
- `step`：Schema 理解、关联推理、SQL 生成、SQL 执行、自修复、图表建议、深度分析等步骤状态。
- `token`：深度分析阶段的流式文本片段。
- `result`：最终结构化结果，包括 SQL、表格预览、图表配置和业务洞察。
- `error`：可恢复错误，前端可展示重试或修改问题入口。
- `done`：本轮任务结束。

## 6. 当前 Demo 的技术边界

- 任务状态当前保存在内存中，适合本地 demo；如果要上线，需要换成数据库表。
- SQL 执行统一走只读校验，并自动加行数限制。
- 多轮上下文当前使用上一轮 `question/sql/analysis` 作为追问补全依据。
- 数据源可以来自默认 CSV、上传文件、SQLite 或 SQLAlchemy URL；MySQL demo 通过 SQLAlchemy URL 接入。
- 后端不会暴露模型推理链路，只向前端输出可展示证据、SQL、结果和洞察。
