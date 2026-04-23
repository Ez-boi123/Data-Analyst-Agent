import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { sampleTask } from "@/lib/sample-task";
import { AnalysisWorkbench } from "./analysis-workbench";

describe("AnalysisWorkbench", () => {
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
});
