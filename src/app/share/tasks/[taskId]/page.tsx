import Link from "next/link";
import { GitBranch, MessageSquare } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { ResultTable } from "@/components/workbench/result-table";
import { InsightChart } from "@/components/workbench/insight-chart";
import { sampleTask } from "@/lib/sample-task";
import { getTask } from "@/lib/api";

type ShareTaskPageProps = {
  params: Promise<{ taskId: string }>;
};

export default async function ShareTaskPage({ params }: ShareTaskPageProps) {
  const { taskId } = await params;
  const task = await getTask(taskId).catch(() => sampleTask);
  const insight = task.steps.find((step) => step.details.insight)?.details.insight;
  const rows = task.steps.flatMap((step) => step.details.resultRows ?? []);

  return (
    <AppShell active="/">
      <PageHeader
        eyebrow="Shared Task"
        title={`${task.title} · 分享页`}
        subtitle="有权限成员可以审阅证据链、评论结论并继续追问，追问会生成新的分析分支。"
        actions={
          <Link className="button primary" href={`/tasks/${task.id}`}>
            返回工作台
          </Link>
        }
      />

      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header">
          <strong>结论</strong>
          <span className="status-pill">可分享 · 有权限可见</span>
        </div>
        <div className="panel-body">
          <h2 style={{ marginTop: 0 }}>{insight?.headline}</h2>
          <div className="two-col">
            <ul className="evidence-list">
              {insight?.evidence.map((item) => <li key={item}>{item}</li>)}
            </ul>
            <ul className="evidence-list">
              {insight?.recommendedNextSteps.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </div>
      </section>

      <div className="two-col">
        <section className="panel">
          <div className="panel-body">{insight && <InsightChart insight={insight} />}</div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <strong>评论与追问</strong>
            <button className="button" type="button">
              <MessageSquare size={16} />
              继续追问
            </button>
          </div>
          <div className="panel-body">
            {task.comments.map((comment) => (
              <div key={comment.id} className="message">
                <strong>{comment.author}</strong>
                <p>{comment.body}</p>
              </div>
            ))}
            <h3>
              <GitBranch size={17} style={{ verticalAlign: "text-bottom" }} /> 分析分支
            </h3>
            <ul className="evidence-list">
              {task.branches.map((branch) => (
                <li key={branch.id}>
                  {branch.title}：{branch.delta}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="panel" style={{ marginTop: 16 }}>
        <div className="panel-body">
          <ResultTable rows={rows.slice(0, 7)} />
        </div>
      </section>
    </AppShell>
  );
}
