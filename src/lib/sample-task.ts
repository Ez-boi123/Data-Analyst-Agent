import type {
  AnalysisStep,
  AnalysisTask,
  AuditSummary,
  DataSource,
  GlossaryMetric,
  ResultRow,
  SchemaEvidence
} from "./types";

const schemaEvidence: SchemaEvidence = {
  tables: [
    {
      id: "orders",
      name: "fact_orders",
      domain: "交易域",
      reason: "GMV、订单数和支付状态的事实来源",
      confidence: 0.96,
      fields: [
        { name: "order_id", type: "string" },
        { name: "user_id", type: "string", sensitive: true },
        { name: "paid_amount", type: "decimal" },
        { name: "region_id", type: "string" },
        { name: "paid_at", type: "timestamp" }
      ]
    },
    {
      id: "regions",
      name: "dim_region",
      domain: "组织域",
      reason: "定位华东区和城市层级",
      confidence: 0.92,
      fields: [
        { name: "region_id", type: "string" },
        { name: "region_name", type: "string" },
        { name: "city_tier", type: "string" }
      ]
    },
    {
      id: "traffic",
      name: "fact_traffic_sessions",
      domain: "流量域",
      reason: "解释转化率下降和渠道贡献变化",
      confidence: 0.89,
      fields: [
        { name: "session_id", type: "string" },
        { name: "channel", type: "string" },
        { name: "region_id", type: "string" },
        { name: "converted_order_id", type: "string" }
      ]
    },
    {
      id: "refunds",
      name: "fact_refunds",
      domain: "交易域",
      reason: "校验退款率是否影响净 GMV",
      confidence: 0.84,
      fields: [
        { name: "order_id", type: "string" },
        { name: "refund_amt", type: "decimal" },
        { name: "refund_reason", type: "string" }
      ]
    }
  ],
  fields: ["paid_amount", "region_name", "channel", "paid_at", "refund_amt"],
  joinPaths: [
    {
      from: "fact_orders.region_id",
      to: "dim_region.region_id",
      condition: "orders.region_id = region.region_id",
      confidence: 0.95
    },
    {
      from: "fact_traffic_sessions.converted_order_id",
      to: "fact_orders.order_id",
      condition: "traffic.converted_order_id = orders.order_id",
      confidence: 0.88
    },
    {
      from: "fact_refunds.order_id",
      to: "fact_orders.order_id",
      condition: "refunds.order_id = orders.order_id",
      confidence: 0.9
    }
  ],
  metricDefinitions: [
    {
      metric: "GMV",
      definition: "支付成功订单的 paid_amount 汇总，不扣除退款。",
      owner: "交易数据组"
    },
    {
      metric: "转化率",
      definition: "支付订单数 / 访问会话数，按渠道和自然日聚合。",
      owner: "增长分析组"
    }
  ],
  filters: ["region_name = '华东区'", "paid_at >= 当前日期 - 7 天", "pay_status = 'PAID'"],
  assumptions: ["使用业务默认 GMV 口径", "对比前 7 天作为基准期", "退款影响作为辅助解释"]
};

const sql = `SELECT
  DATE(o.paid_at) AS date,
  r.region_name AS region,
  t.channel,
  SUM(o.paid_amount) AS gmv,
  COUNT(DISTINCT o.order_id) AS orders,
  COUNT(DISTINCT o.order_id) / NULLIF(COUNT(DISTINCT t.session_id), 0) AS conversion_rate,
  SUM(COALESCE(f.refund_amt, 0)) / NULLIF(SUM(o.paid_amount), 0) AS refund_rate
FROM fact_orders o
JOIN dim_region r ON o.region_id = r.region_id
LEFT JOIN fact_traffic_sessions t ON t.converted_order_id = o.order_id
LEFT JOIN fact_refunds f ON f.order_id = o.order_id
WHERE r.region_name = '华东区'
  AND o.paid_at >= CURRENT_DATE - INTERVAL '7 days'
  AND o.pay_status = 'PAID'
GROUP BY 1, 2, 3
ORDER BY 1, 3;`;

export const resultRows: ResultRow[] = [
  { date: "04-11", region: "华东区", channel: "搜索", gmv: 128.4, orders: 18420, conversionRate: 5.8, refundRate: 1.8 },
  { date: "04-12", region: "华东区", channel: "搜索", gmv: 121.2, orders: 17660, conversionRate: 5.4, refundRate: 1.9 },
  { date: "04-13", region: "华东区", channel: "推荐", gmv: 118.7, orders: 16980, conversionRate: 4.9, refundRate: 2.1 },
  { date: "04-14", region: "华东区", channel: "推荐", gmv: 109.3, orders: 15220, conversionRate: 4.3, refundRate: 2.3 },
  { date: "04-15", region: "华东区", channel: "广告", gmv: 101.8, orders: 14110, conversionRate: 3.9, refundRate: 2.4 },
  { date: "04-16", region: "华东区", channel: "广告", gmv: 96.5, orders: 13390, conversionRate: 3.6, refundRate: 2.5 },
  { date: "04-17", region: "华东区", channel: "推荐", gmv: 93.2, orders: 12970, conversionRate: 3.4, refundRate: 2.6 }
];

const audit: AuditSummary = {
  initiator: "Lina Chen",
  dataDomainsUsed: ["交易域", "商品域", "流量域"],
  sqlGenerated: 3,
  sqlExecuted: 2,
  repairCount: 2,
  sharedWith: ["华东运营组", "数据分析组"],
  followUps: 2
};

export const sampleTask: AnalysisTask = {
  id: "task-gmv-east-7d",
  title: "华东区 GMV 下滑归因",
  question: "为什么华东区最近 7 天 GMV 下滑？",
  status: "completed",
  businessDomain: "经营分析 / 交易域",
  createdBy: "Lina Chen",
  createdAt: "2026-04-17T09:20:00+08:00",
  updatedAt: "2026-04-17T09:38:00+08:00",
  permissionsSummary: "交易域、商品域、流量域；敏感用户字段已脱敏",
  shareState: "shared",
  audit,
  branches: [
    {
      id: "branch-channel",
      title: "追问：广告渠道是否异常？",
      summary: "广告渠道 GMV 下降 18.7%，主要由转化率下降驱动。",
      delta: "较原结论增加渠道拆解"
    },
    {
      id: "branch-city-tier",
      title: "追问：是否集中在二线城市？",
      summary: "二线城市贡献 61% 的跌幅，客单价基本稳定。",
      delta: "较原结论增加城市层级维度"
    }
  ],
  comments: [
    {
      id: "comment-1",
      author: "Mia Wang",
      body: "请继续看一下广告渠道预算调整是否发生在 04-14。",
      createdAt: "2026-04-17T09:42:00+08:00"
    },
    {
      id: "comment-2",
      author: "Rui Zhang",
      body: "口径确认：GMV 先不扣退款，退款作为辅助解释即可。",
      createdAt: "2026-04-17T09:45:00+08:00"
    }
  ],
  steps: [
    {
      id: "step-clarifying",
      type: "clarifying",
      status: "completed",
      title: "批量澄清关键条件",
      summary: "确认业务域、时间范围和 GMV 口径，使用系统推荐默认值继续分析。",
      evidence: ["业务域：经营分析 / 交易域", "时间范围：最近 7 天，对比前 7 天", "GMV：支付成功金额，不扣退款"],
      confidence: 0.93,
      details: { schema: schemaEvidence }
    },
    {
      id: "step-understanding",
      type: "understanding",
      status: "completed",
      title: "理解问题并生成计划",
      summary: "将问题拆成趋势确认、维度拆解、渠道贡献、退款辅助验证四个分析动作。",
      evidence: ["先确认 GMV 是否显著下降", "再按渠道和城市层级定位贡献", "最后校验退款率影响"],
      confidence: 0.91,
      details: {}
    },
    {
      id: "step-schema",
      type: "schema_retrieval",
      status: "completed",
      title: "检索相关 Schema",
      summary: "命中 4 张核心表，覆盖订单、区域、流量和退款。",
      evidence: ["fact_orders 提供 GMV", "dim_region 定位华东区", "fact_traffic_sessions 提供转化率"],
      confidence: 0.92,
      details: { schema: schemaEvidence }
    },
    {
      id: "step-relation",
      type: "relation_reasoning",
      status: "completed",
      title: "推理表关联路径",
      summary: "使用订单表作为中心事实表，连接区域、流量和退款数据。",
      evidence: ["orders.region_id -> region.region_id", "traffic.converted_order_id -> orders.order_id", "refunds.order_id -> orders.order_id"],
      confidence: 0.9,
      details: { schema: schemaEvidence }
    },
    {
      id: "step-sql-generation",
      type: "sql_generation",
      status: "completed",
      title: "生成只读 SQL",
      summary: "生成 SELECT 查询，默认限行 500，超时 30 秒。",
      evidence: ["只读沙箱", "字段脱敏", "行数限制 500"],
      confidence: 0.88,
      details: {
        sql: {
          sql,
          safetyStatus: ["只读 SELECT", "行数限制 500", "超时 30s", "敏感字段脱敏", "业务域权限过滤"],
          rowLimit: 500,
          timeoutMs: 30000,
          executionStatus: "success",
          repairAttempts: [],
          durationMs: 1260
        }
      }
    },
    {
      id: "step-sql-execution",
      type: "sql_execution",
      status: "completed",
      title: "执行 SQL 并预览结果",
      summary: "查询返回 128 行，前端仅展示分页预览和字段类型。",
      evidence: ["返回 128 行", "预览 7 行", "结果表支持分页和列控制"],
      confidence: 0.87,
      details: {
        resultRows,
        sql: {
          sql,
          safetyStatus: ["只读 SELECT", "行数限制 500", "超时 30s", "敏感字段脱敏", "业务域权限过滤"],
          rowLimit: 500,
          timeoutMs: 30000,
          executionStatus: "success",
          repairAttempts: [],
          durationMs: 1260
        }
      }
    },
    {
      id: "step-repair",
      type: "sql_repairing",
      status: "completed",
      title: "SQL 错误自修复",
      summary: "首次执行引用了旧字段 refund_amount，Agent 根据 Schema 修复为 refund_amt 后重试成功。",
      evidence: ["错误原因：字段不存在", "修复动作：改用 fact_refunds.refund_amt", "重试成功"],
      confidence: 0.86,
      details: {
        sql: {
          sql,
          safetyStatus: ["只读 SELECT", "行数限制 500", "超时 30s", "敏感字段脱敏", "业务域权限过滤"],
          rowLimit: 500,
          timeoutMs: 30000,
          executionStatus: "success",
          errorSummary: "字段不存在：fact_refunds.refund_amount。Schema 中可用字段为 refund_amt。",
          repairAttempts: [
            { attempt: 1, summary: "将 refund_amount 映射到候选字段 refund_amt", status: "failed" },
            { attempt: 2, summary: "同步更新聚合表达式并重新执行", status: "success" }
          ],
          sqlDiff: `-  refund_amount
+  refund_amt`,
          durationMs: 1820
        }
      }
    },
    {
      id: "step-insight",
      type: "insight_generation",
      status: "completed",
      title: "生成图表、结论和建议",
      summary: "GMV 7 天下降 27.4%，主要由推荐和广告渠道转化率下降驱动。",
      evidence: ["GMV 从 128.4 万降至 93.2 万", "转化率从 5.8% 降至 3.4%", "退款率小幅上升但不是主因"],
      confidence: 0.89,
      details: {
        resultRows,
        insight: {
          chartType: "line",
          chartConfig: {
            title: "华东区 GMV 趋势",
            categories: resultRows.map((row) => row.date),
            series: [
              { name: "GMV(万)", data: resultRows.map((row) => row.gmv) },
              { name: "转化率(%)", data: resultRows.map((row) => row.conversionRate) }
            ]
          },
          headline: "华东区 GMV 下降主要由推荐和广告渠道转化率下滑驱动。",
          evidence: ["7 天 GMV 下降 27.4%", "推荐渠道贡献 42% 跌幅", "退款率仅上升 0.8 个百分点"],
          possibleCauses: ["推荐流量质量下降", "广告渠道预算或素材调整", "二线城市活动结束造成需求回落"],
          recommendedNextSteps: ["追问广告渠道预算变化", "按城市层级拆解推荐流量", "检查 04-14 后活动配置变更"]
        }
      }
    },
    {
      id: "step-completed",
      type: "completed",
      status: "completed",
      title: "完成并生成可分享任务页",
      summary: "任务已完成，可分享给有权限成员评论或发起追问分支。",
      evidence: ["分享对象：华东运营组、数据分析组", "已有 2 个追问分支", "任务级审计已生成"],
      confidence: 0.94,
      details: { audit }
    }
  ]
};

export function getRecoverableFailureStep(): AnalysisStep {
  return {
    id: "step-failed-recoverable",
    type: "failed_recoverable",
    status: "failed_recoverable",
    title: "业务口径不足，等待恢复",
    summary: "当前指标口径缺少退款处理规则，继续执行可能导致结论偏差。",
    evidence: ["GMV 口径存在扣除退款和不扣退款两种定义", "业务词典未找到当前业务域默认口径"],
    confidence: 0.62,
    details: {
      recoveryActions: ["补充指标口径", "改选业务域", "缩短时间范围", "重试分析"]
    }
  };
}

export function getTaskAuditItems(task: AnalysisTask): string[] {
  return [
    `发起人：${task.audit.initiator}`,
    `使用数据域：${task.audit.dataDomainsUsed.join("、")}`,
    `生成 SQL：${task.audit.sqlGenerated} 次`,
    `执行 SQL：${task.audit.sqlExecuted} 次`,
    `自修复：${task.audit.repairCount} 次`,
    `分享对象：${task.audit.sharedWith.join("、")}`,
    `追问分支：${task.audit.followUps} 个`
  ];
}

export const dataSources: DataSource[] = [
  { id: "ds-trade", name: "交易数仓", domain: "交易域", status: "synced", tables: 42, fields: 628, lastSync: "2026-04-17 08:45" },
  { id: "ds-traffic", name: "增长行为库", domain: "流量域", status: "syncing", tables: 27, fields: 394, lastSync: "同步中" },
  { id: "ds-product", name: "商品主数据", domain: "商品域", status: "attention", tables: 18, fields: 216, lastSync: "2026-04-16 23:10" }
];

export const glossaryMetrics: GlossaryMetric[] = [
  { id: "gmv", metric: "GMV", definition: "支付成功订单金额汇总，不扣除退款。", owner: "交易数据组", freshness: "每日 08:30 更新" },
  { id: "conversion", metric: "转化率", definition: "支付订单数 / 访问会话数，按自然日和渠道聚合。", owner: "增长分析组", freshness: "小时级更新" },
  { id: "refund", metric: "退款率", definition: "退款金额 / 支付金额，用于辅助解释净收入变化。", owner: "财务分析组", freshness: "每日 09:00 更新" }
];
