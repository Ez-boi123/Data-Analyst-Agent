# SPEC.md — Data Analyst Agent Web UI 技术规范

## 1. 产品定位与范围

Data Analyst Agent Web UI 是一个面向业务负责人的智能数据分析工作台，解决多业务、多表场景下数据理解难、表关联不透明、SQL 分析效率低、结果难复盘的问题。

v1 采用 `左侧 Agent 对话 + 右侧结构化分析工作区` 的 Hybrid 形态。核心产物是“分析任务”，而不是单次聊天消息或静态报表。每个任务沉淀用户问题、业务口径、Schema 证据、表关联路径、SQL、执行/修复记录、结果表、图表、洞察、评论和追问分支。

v1 页面范围：

- 分析任务列表与新建分析
- 分析工作台
- 可分享任务页
- 数据源 / Schema 轻量管理
- 业务词典 / 指标口径
- 基础设置
- 内置“经营指标异动分析”样例任务

v1 明确不做：

- 完整 BI 拖拽编辑器
- 可编辑数据建模器
- 多人实时协同编辑
- 完整数据治理平台
- 移动端完整 SQL / Schema 操作

## 2. 技术栈与前端架构

采用产品级 Web 应用技术栈：

- `Next.js + React + TypeScript`，使用 App Router。
- `Tailwind CSS + shadcn/ui` 作为组件和样式基础。
- `React Flow` 用于 Schema 关系与 Join 路径可解释图。
- `TanStack Table` 用于 SQL 结果表预览、分页、列控制。
- `Apache ECharts` 用于趋势、对比、分布、贡献度等分析图表。
- `Zustand` 用于工作台内轻量客户端状态，例如当前任务、展开步骤、选中图表、Drawer 状态。
- `next-intl` 支持中英双语，默认中文，保留 `SQL / Schema / Join / Agent` 等英文技术术语。

建议路由：

- `/`：任务首页，可查看最近任务与创建分析
- `/tasks/new`：新建分析任务
- `/tasks/[taskId]`：分析工作台
- `/share/tasks/[taskId]`：可分享任务页
- `/data-sources`：数据源与 Schema 同步状态
- `/glossary`：业务词典与指标口径
- `/settings`：语言、权限视图、偏好设置

页面布局：

- 桌面端优先，工作台最小建议宽度 `1280px`。
- 移动端只支持任务审阅、结论、图表、评论和分享页，不支持复杂 SQL / Schema 编辑。
- 整体视觉为“清醒专业”：浅色为主，中高信息密度，避免传统后台感和暗色指挥舱风格。

## 3. 核心页面与交互规范

分析工作台采用三栏/双区结构：

- 左侧：Agent 对话区，包含用户问题、Agent 澄清、阶段进展、追问入口。
- 中/右主区：证据时间线，按分析阶段展示。
- 详情区：点击某个阶段后展开结构化详情，内部使用标签页组织 `口径 / Schema / SQL / 结果 / 洞察 / 审计`。

分析阶段状态机：

- `clarifying`：澄清业务域、时间范围、指标口径、筛选条件
- `understanding`：理解问题与生成分析计划
- `schema_retrieval`：检索相关表、字段、指标
- `relation_reasoning`：推理 Join 路径与过滤条件
- `sql_generation`：生成 SQL
- `sql_execution`：只读沙箱执行
- `sql_repairing`：错误自修复
- `insight_generation`：生成图表、结论、证据和建议
- `completed`：完成，可分享、评论、追问
- `failed_recoverable`：可恢复失败，允许补充信息、改业务域、重试

可信证据默认展示：

- 业务问题理解
- 指标口径与假设
- 使用的数据源、业务域和权限范围
- 相关表及选择原因
- Join 路径、主外键或推断关系、置信度
- 时间范围、过滤条件、分组维度
- 关键结论的数据证据

专家能力采用渐进展开：

- SQL 默认折叠，用户可查看格式化 SQL。
- SQL 报错时默认展示错误摘要、修复动作和最终状态。
- 可展开查看 SQL Diff、重试历史和执行耗时。
- 不展示原始模型思维链，只展示证据化解释。

新建分析任务：

- 输入方式为“自由输入 + 轻量问题向导”。
- Agent 只批量询问 1-3 个会影响 SQL 或结论的关键澄清问题。
- 每个澄清问题必须带推荐默认值。
- 默认演示问题：`为什么华东区最近 7 天 GMV 下滑？`

图表与洞察：

- Agent 自动推荐图表，用户可轻编辑图表类型、维度、指标、时间粒度。
- 图表旁必须展示“结论 + 证据 + 建议”。
- 支持图表导出图片，任务页整体 v1 以分享链接为主，PDF/PPT 可作为后续增强。

结果表：

- 默认展示预览数据，不全量渲染大结果集。
- 必须显示行数限制、字段类型、分页、列显示控制和导出入口。
- 大结果集由后端分页或采样，前端不得一次性加载完整数据。

协作与版本：

- 分享页支持有权限用户查看、评论和继续追问。
- 追问生成分析分支，不覆盖原任务。
- 任务页需要展示分支来源，并支持对比原结论与新结论差异。

失败体验：

- 失败必须落在具体阶段。
- UI 显示失败原因、影响范围和可恢复动作。
- 用户可补充口径、改选业务域、调整时间范围或重试。
- 不允许只显示“分析失败”这种死胡同状态。

## 4. 前端视图模型

`AnalysisTask`：

- `id`
- `title`
- `question`
- `status`
- `businessDomain`
- `createdBy`
- `createdAt`
- `updatedAt`
- `permissionsSummary`
- `steps`
- `branches`
- `comments`
- `shareState`

`AnalysisStep`：

- `id`
- `type`
- `status`
- `title`
- `summary`
- `evidence`
- `confidence`
- `startedAt`
- `finishedAt`
- `details`

`SchemaEvidence`：

- `tables`
- `fields`
- `joinPaths`
- `metricDefinitions`
- `filters`
- `assumptions`

`SqlExecutionView`：

- `sql`
- `safetyStatus`
- `rowLimit`
- `timeoutMs`
- `executionStatus`
- `errorSummary`
- `repairAttempts`
- `sqlDiff`
- `durationMs`

`InsightView`：

- `chartType`
- `chartConfig`
- `headline`
- `evidence`
- `possibleCauses`
- `recommendedNextSteps`

`AuditSummary`：

- `initiator`
- `dataDomainsUsed`
- `sqlGenerated`
- `sqlExecuted`
- `repairCount`
- `sharedWith`
- `followUps`

这些是前端页面所需视图模型，不规定后端 Agent 内部实现。

## 5. 安全、权限与国际化

SQL 安全：

- UI 明确显示只读沙箱状态。
- 只允许 `SELECT` 类只读查询。
- 默认展示限行、超时、脱敏、权限过滤状态。
- 敏感字段在 Schema 图和结果表中必须标识或脱敏。

权限：

- v1 使用业务域权限模型。
- 用户只能分析有权限的数据源、表和字段。
- 任务页必须显示本次分析使用的授权范围。
- 分享页只允许有权限用户访问。

审计：

- v1 做任务级审计。
- 记录并展示谁发起、使用哪些数据域、生成/执行哪些 SQL、修复次数、谁分享、谁追问。
- 不做点击级完整操作审计。

国际化：

- 默认中文界面。
- 支持中英切换。
- 文案使用 i18n key 管理。
- 日期、数字、百分比、货币按 locale 格式化。
- 技术术语采用中文解释 + 英文标签，例如 `表结构 Schema`、`关联路径 Join Path`。

## 6. 验收标准与测试场景

核心验收目标：完整链路可演示。

必须通过的主路径：

- 用户创建经营指标异动分析任务。
- Agent 批量澄清关键条件。
- 工作台展示阶段状态机。
- Schema 图展示相关表和 Join 路径。
- 证据时间线展示业务口径、表路径、过滤条件和置信度。
- SQL 生成后以折叠方式展示。
- 模拟一次 SQL 报错，并展示修复摘要、SQL Diff、重试成功。
- 结果表以分页/预览形式展示。
- 图表展示 GMV 趋势和维度拆解。
- 洞察区输出结论、证据和建议。
- 任务完成后可分享、评论、追问，并生成分析分支。

状态测试：

- 空数据源
- 无权限业务域
- Schema 同步中
- SQL 执行超时
- SQL 自修复成功
- SQL 自修复失败但可恢复
- 大结果集分页
- 移动端分享页审阅
- 中英文切换
- 无图表数据时的降级展示

质量要求：

- 桌面端工作台不出现横向页面滚动，结果表内部可横向滚动。
- 关键操作有 loading、success、failed、retry 状态。
- 证据时间线每个阶段都可折叠/展开。
- 所有图表有空状态和数据不足说明。
- 表格、按钮、输入框、Tabs、Drawer、Dialog 使用一致的 shadcn/ui 风格。
- 不展示原始模型思维链，只展示证据化解释。

## 7. 参考文档

- [Next.js App Router Docs](https://nextjs.org/docs/app)
- [shadcn/ui Docs](https://ui.shadcn.com/docs)
- [TanStack Table Docs](https://tanstack.com/table/docs)
- [React Flow Docs](https://reactflow.dev/learn/concepts/core-concepts)
- [Apache ECharts](https://echarts.apache.org/en/index.html)
- [next-intl](https://next-intl.dev/)
- [Zustand Introduction](https://www.mintlify.com/pmndrs/zustand/introduction)