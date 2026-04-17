import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PromptTaskComposer } from "@/components/tasks/prompt-task-composer";
import { sampleTask } from "@/lib/sample-task";

export default function HomePage() {
  return (
    <AppShell active="/">
      <section className="tasks-home-hero">
        <div>
          <div className="eyebrow">Analysis Tasks</div>
          <h1 className="title agent-title">数据分析Agent</h1>
          <p className="agent-intro">
            从业务问题到可信洞察，自动理解 Schema、推理 Join、生成 SQL，并完成错误自修复。
          </p>
        </div>
        <PromptTaskComposer />
      </section>

      <section className="panel tasks-history">
        <div className="panel-header">
          <strong>历史任务</strong>
          <span className="status-pill">内置样例任务</span>
        </div>
        <div className="task-row">
          <div>
            <h2 style={{ margin: "0 0 8px" }}>{sampleTask.title}</h2>
            <p className="subtitle" style={{ margin: 0 }}>
              {sampleTask.question} · {sampleTask.permissionsSummary}
            </p>
            <div className="tabs">
              <span className="status-pill">证据时间线</span>
              <span className="status-pill">SQL Diff</span>
              <span className="status-pill">图表洞察</span>
              <span className="status-pill">2 个追问分支</span>
            </div>
          </div>
          <Link aria-label="打开工作台" className="button primary icon-button" href={`/tasks/${sampleTask.id}`}>
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
