import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { dataSources } from "@/lib/sample-task";
import { listDataSources } from "@/lib/api";

export default async function DataSourcesPage() {
  const sources = await listDataSources().catch(() => dataSources);

  return (
    <AppShell active="/data-sources">
      <PageHeader
        eyebrow="Data Sources"
        title="数据源 / Schema"
        subtitle="轻量管理数据源连接状态、Schema 同步和业务域权限，不做完整 DBA 或数据治理平台。"
      />
      <section className="list-grid">
        {sources.map((source) => (
          <article key={source.id} className="panel task-row">
            <div>
              <h2 style={{ margin: "0 0 8px" }}>{source.name}</h2>
              <p className="subtitle" style={{ margin: 0 }}>
                {source.domain} · {source.tables} 张表 · {source.fields} 个字段 · 上次同步：{source.lastSync}
              </p>
            </div>
            <span className={`status-pill ${source.status === "attention" ? "warning" : ""}`}>
              {source.status === "synced" ? "已同步" : source.status === "syncing" ? "同步中" : "需关注"}
            </span>
          </article>
        ))}
      </section>
    </AppShell>
  );
}
