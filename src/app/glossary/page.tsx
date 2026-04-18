import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { glossaryMetrics } from "@/lib/sample-task";
import { listGlossaryMetrics } from "@/lib/api";

export default async function GlossaryPage() {
  const metrics = await listGlossaryMetrics().catch(() => glossaryMetrics);

  return (
    <AppShell active="/glossary">
      <PageHeader
        eyebrow="Business Glossary"
        title="业务词典 / 指标口径"
        subtitle="让 Agent 在生成 SQL 之前先理解指标定义、业务口径和负责人。"
      />
      <section className="list-grid">
        {metrics.map((metric) => (
          <article key={metric.id} className="panel">
            <div className="panel-header">
              <strong>{metric.metric}</strong>
              <span className="status-pill">{metric.owner}</span>
            </div>
            <div className="panel-body">
              <p>{metric.definition}</p>
              <p className="subtitle">{metric.freshness}</p>
            </div>
          </article>
        ))}
      </section>
    </AppShell>
  );
}
