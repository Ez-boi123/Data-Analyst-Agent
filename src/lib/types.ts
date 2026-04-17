export type Locale = "zh" | "en";

export type TaskStatus =
  | "clarifying"
  | "understanding"
  | "schema_retrieval"
  | "relation_reasoning"
  | "sql_generation"
  | "sql_execution"
  | "sql_repairing"
  | "insight_generation"
  | "completed"
  | "failed_recoverable";

export type StepStatus = "waiting" | "running" | "completed" | "failed_recoverable";

export type AnalysisStepType = TaskStatus;

export type SchemaTable = {
  id: string;
  name: string;
  domain: string;
  reason: string;
  confidence: number;
  fields: Array<{
    name: string;
    type: string;
    sensitive?: boolean;
  }>;
};

export type SchemaEvidence = {
  tables: SchemaTable[];
  fields: string[];
  joinPaths: Array<{
    from: string;
    to: string;
    condition: string;
    confidence: number;
  }>;
  metricDefinitions: Array<{
    metric: string;
    definition: string;
    owner: string;
  }>;
  filters: string[];
  assumptions: string[];
};

export type SqlExecutionView = {
  sql: string;
  safetyStatus: string[];
  rowLimit: number;
  timeoutMs: number;
  executionStatus: "pending" | "failed" | "success";
  errorSummary?: string;
  repairAttempts: Array<{
    attempt: number;
    summary: string;
    status: "failed" | "success";
  }>;
  sqlDiff?: string;
  durationMs: number;
};

export type InsightView = {
  chartType: "line" | "bar" | "pie";
  chartConfig: {
    title: string;
    categories: string[];
    series: Array<{
      name: string;
      data: number[];
    }>;
  };
  headline: string;
  evidence: string[];
  possibleCauses: string[];
  recommendedNextSteps: string[];
};

export type AuditSummary = {
  initiator: string;
  dataDomainsUsed: string[];
  sqlGenerated: number;
  sqlExecuted: number;
  repairCount: number;
  sharedWith: string[];
  followUps: number;
};

export type AnalysisStep = {
  id: string;
  type: AnalysisStepType;
  status: StepStatus;
  title: string;
  summary: string;
  evidence: string[];
  confidence: number;
  startedAt?: string;
  finishedAt?: string;
  details: {
    schema?: SchemaEvidence;
    sql?: SqlExecutionView;
    insight?: InsightView;
    audit?: AuditSummary;
    resultRows?: ResultRow[];
    recoveryActions?: string[];
  };
};

export type ResultRow = {
  date: string;
  region: string;
  channel: string;
  gmv: number;
  orders: number;
  conversionRate: number;
  refundRate: number;
};

export type AnalysisTask = {
  id: string;
  title: string;
  question: string;
  status: TaskStatus;
  businessDomain: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  permissionsSummary: string;
  steps: AnalysisStep[];
  branches: Array<{
    id: string;
    title: string;
    summary: string;
    delta: string;
  }>;
  comments: Array<{
    id: string;
    author: string;
    body: string;
    createdAt: string;
  }>;
  shareState: "private" | "shared";
  audit: AuditSummary;
};

export type DataSource = {
  id: string;
  name: string;
  domain: string;
  status: "synced" | "syncing" | "attention";
  tables: number;
  fields: number;
  lastSync: string;
};

export type GlossaryMetric = {
  id: string;
  metric: string;
  definition: string;
  owner: string;
  freshness: string;
};
