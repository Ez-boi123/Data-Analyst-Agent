# Data Analyst Agent Web UI 技术规范

## 产品定位

Data Analyst Agent Web UI 是面向业务负责人的智能数据分析工作台，聚焦多业务、多表场景下的数据理解、表关联推理、SQL 生成、自修复、图表洞察和任务复盘。

v1 采用左侧 Agent 对话 + 右侧结构化分析工作区的 Hybrid 形态。核心产物是分析任务，每个任务沉淀用户问题、业务口径、Schema 证据、Join 路径、SQL、执行/修复记录、结果表、图表、洞察、评论和追问分支。

## 技术栈

- Next.js App Router + React + TypeScript
- Tailwind CSS + shadcn/ui 风格组件
- React Flow 用于 Schema / Join Path 可解释图
- TanStack Table 用于结果表预览、分页和列控制
- Apache ECharts 用于趋势与拆解图表
- Zustand 预留工作台客户端状态
- next-intl 预留中英双语能力，默认中文，保留 SQL / Schema / Join / Agent 等技术术语

## 页面范围

- `/`：分析任务首页
- `/tasks/new`：新建分析任务
- `/tasks/[taskId]`：分析工作台
- `/share/tasks/[taskId]`：可分享任务页
- `/data-sources`：数据源与 Schema 同步状态
- `/glossary`：业务词典与指标口径
- `/settings`：语言、权限和偏好设置

## 核心交互

- 分析工作台展示 Agent 对话、证据时间线、阶段详情、SQL 自修复、结果预览和分享入口。
- 阶段详情使用口径、Schema、SQL、结果、洞察、审计标签组织。
- Schema 图展示相关表、业务域、Join 路径和置信度，不做 v1 可编辑建模。
- SQL 默认折叠在专家详情中，失败时展示错误摘要、SQL Diff 和重试历史。
- 图表洞察采用结论 + 证据 + 建议的结构。
- 分享页支持审阅、评论和继续追问，追问以分析分支表达，不覆盖原任务。

## v1 边界

v1 不做完整 BI 拖拽编辑器、可编辑数据建模器、多人实时协同编辑、完整数据治理平台，也不在移动端支持复杂 SQL / Schema 操作。

## 验收主路径

用户可以从首页打开内置样例任务“华东区 GMV 下滑归因”，看到：

- 批量澄清关键条件
- 证据时间线和阶段状态
- Schema / Join Path 解释
- 只读 SQL 安全状态
- SQL 报错后的自修复摘要和 Diff
- 结果表分页预览
- GMV 趋势洞察
- 分享页、评论和分析分支
