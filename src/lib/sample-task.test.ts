import { describe, expect, it } from "vitest";
import { sampleTask, getRecoverableFailureStep, getTaskAuditItems } from "./sample-task";

describe("sample analysis task", () => {
  it("contains the complete operating metric investigation path", () => {
    expect(sampleTask.question).toContain("华东区");
    expect(sampleTask.steps.map((step) => step.type)).toEqual([
      "clarifying",
      "understanding",
      "schema_retrieval",
      "relation_reasoning",
      "sql_generation",
      "sql_execution",
      "sql_repairing",
      "insight_generation",
      "completed"
    ]);
  });

  it("models SQL self repair with a diff and retry history", () => {
    const repairStep = sampleTask.steps.find((step) => step.type === "sql_repairing");

    expect(repairStep?.details.sql?.errorSummary).toContain("字段不存在");
    expect(repairStep?.details.sql?.sqlDiff).toContain("-  refund_amount");
    expect(repairStep?.details.sql?.repairAttempts).toHaveLength(2);
    expect(repairStep?.details.sql?.executionStatus).toBe("success");
  });

  it("exposes recoverable failure information instead of a dead-end state", () => {
    const failedStep = getRecoverableFailureStep();

    expect(failedStep.status).toBe("failed_recoverable");
    expect(failedStep.details.recoveryActions).toEqual([
      "补充指标口径",
      "改选业务域",
      "缩短时间范围",
      "重试分析"
    ]);
  });

  it("summarizes task-level audit records", () => {
    expect(getTaskAuditItems(sampleTask)).toEqual([
      "发起人：Lina Chen",
      "使用数据域：交易域、商品域、流量域",
      "生成 SQL：3 次",
      "执行 SQL：2 次",
      "自修复：2 次",
      "分享对象：华东运营组、数据分析组",
      "追问分支：2 个"
    ]);
  });
});
