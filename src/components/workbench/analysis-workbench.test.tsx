import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { sampleTask } from "@/lib/sample-task";
import { AnalysisWorkbench } from "./analysis-workbench";

const apiMocks = vi.hoisted(() => ({
  getTask: vi.fn(),
  streamFollowUp: vi.fn(),
  streamTaskRun: vi.fn()
}));

vi.mock("@/lib/api", () => apiMocks);

describe("AnalysisWorkbench", () => {
  it.each([
    ["waiting", "等待执行"],
    ["running", "运行中"],
    ["completed", "完成"],
    ["failed_recoverable", "可恢复"]
  ] as const)("renders the actual %s timeline status", (status, label) => {
    const step = { ...sampleTask.steps[0], title: "状态验证步骤", status };
    render(React.createElement(AnalysisWorkbench, {
      initialTask: { ...sampleTask, steps: [step] }
    }));

    const card = screen.getByRole("button", { name: /状态验证步骤/ });
    expect(within(card).getByText(label)).toBeInTheDocument();
    if (status !== "completed") {
      expect(within(card).queryByText("完成")).not.toBeInTheDocument();
      expect(card.querySelector(".lucide-circle-check")).toBeNull();
    }
  });

  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
  });

  it("updates repair attempts from streamed steps without counting completion twice", async () => {
    let emit: (event: any) => void = () => {};
    apiMocks.streamTaskRun.mockImplementation((_id, onEvent) => {
      emit = onEvent;
      return new Promise(() => {});
    });
    render(React.createElement(AnalysisWorkbench, {
      initialTask: { ...sampleTask, id: "live-metrics", steps: [sampleTask.steps[0]], audit: { ...sampleTask.audit, repairCount: 0 } },
      autoRun: true
    }));
    const metric = screen.getByText("SQL 自修复").closest(".metric")! as HTMLElement;
    const repair = { ...sampleTask.steps[0], id: "repair-1", type: "sql_repairing", status: "running" };
    act(() => emit({ event: "step", data: repair }));
    expect(within(metric).getByText("1 次")).toBeInTheDocument();
    act(() => emit({ event: "step", data: { ...repair, status: "completed" } }));
    expect(within(metric).getByText("1 次")).toBeInTheDocument();
    act(() => emit({ event: "step", data: { ...repair, id: "repair-2" } }));
    expect(within(metric).getByText("2 次")).toBeInTheDocument();
  });

  it("does not present an unmeasured schema score and separates follow-ups from branches", () => {
    render(React.createElement(AnalysisWorkbench, {
      initialTask: { ...sampleTask, branches: [], audit: { ...sampleTask.audit, followUps: 3 } }
    }));
    const metric = screen.getByText("Schema 置信度").closest(".metric")! as HTMLElement;
    expect(within(metric).getByText("未评估")).toBeInTheDocument();
    expect(screen.getByText("3 次追问 · 0 个分支")).toBeInTheDocument();
  });

  it("renders the assessed score and its explanation from schema evidence", () => {
    const schema = sampleTask.steps.find((step) => step.details.schema?.tables.length)?.details.schema!;
    const assessment = { score: 0.735, method: "测试评分公式", components: { "字段完整性": 0.8 }, warnings: ["关联键存在缺失"], scope: "结构质量规则分，不是正确概率" };
    render(React.createElement(AnalysisWorkbench, {
      initialTask: { ...sampleTask, steps: [{ ...sampleTask.steps[0], details: { schema: { ...schema, assessment } } }] }
    }));
    const metric = screen.getByText("Schema 置信度").closest(".metric")! as HTMLElement;
    expect(within(metric).getByText("74%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Schema" }));
    expect(screen.getByText("测试评分公式")).toBeInTheDocument();
    expect(screen.getByText("关联键存在缺失")).toBeInTheDocument();
  });

  it("renders the hybrid workbench with chat, chart insight, SQL repair, and delivery actions", async () => {
    render(React.createElement(AnalysisWorkbench, { initialTask: sampleTask }));

    expect(screen.getByText("Agent 对话")).toBeInTheDocument();
    expect(screen.getByText("证据时间线")).toBeInTheDocument();
    expect(screen.getAllByText("华东区 GMV 趋势").length).toBeGreaterThan(0);
    expect(screen.getByText("SQL 错误自修复")).toBeInTheDocument();
    expect(screen.getByText("关键证据")).toHaveClass("section-title");

    fireEvent.click(screen.getByRole("button", { name: "Schema" }));
    expect(screen.getByText("fact_orders")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /SQL 错误自修复/ }));
    fireEvent.click(screen.getByRole("button", { name: "SQL" }));

    expect(screen.getByText("字段不存在：fact_refunds.refund_amount。Schema 中可用字段为 refund_amt。")).toBeInTheDocument();
    expect(screen.getByText("结果预览")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /分享任务/ })).toHaveAttribute("href", "/share/tasks/task-gmv-east-7d");
    expect(screen.getByRole("textbox", { name: "输入追问" })).toBeInTheDocument();
  });

  it("replaces the streamed insight with the persisted assistant message", async () => {
    const answer = "这是唯一的最终分析结果。";
    const initialTask = {
      ...sampleTask,
      id: "task-stream-dedup",
      status: "understanding" as const,
      messages: [{ role: "user", content: sampleTask.question, createdAt: sampleTask.createdAt }]
    };
    const completedTask = {
      ...initialTask,
      status: "completed" as const,
      messages: [
        ...initialTask.messages,
        { role: "assistant", content: answer, createdAt: "2026-09-05T19:00:00+08:00" }
      ]
    };

    apiMocks.streamTaskRun.mockImplementation(async (_taskId, onEvent) => {
      onEvent({ event: "token", data: { stepType: "insight_generation", content: answer } });
      onEvent({ event: "task", data: completedTask });
      onEvent({ event: "done", data: { taskId: completedTask.id, status: "completed" } });
    });
    apiMocks.getTask.mockResolvedValue(completedTask);

    render(React.createElement(AnalysisWorkbench, { initialTask, autoRun: true }));

    await waitFor(() => expect(screen.getByText("运行完成")).toBeInTheDocument());
    expect(screen.getAllByText(answer)).toHaveLength(1);
  });
});
