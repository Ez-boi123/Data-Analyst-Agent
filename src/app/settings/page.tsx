import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { dictionaries } from "@/lib/i18n";

export default function SettingsPage() {
  return (
    <AppShell active="/settings">
      <PageHeader
        eyebrow="Settings"
        title="设置"
        subtitle="默认中文界面，保留 SQL / Schema / Join / Agent 等英文技术术语，并预留完整 i18n。"
      />
      <div className="two-col">
        <section className="panel">
          <div className="panel-header">
            <strong>语言</strong>
            <span className="status-pill">中文默认</span>
          </div>
          <div className="panel-body">
            <ul className="evidence-list">
              <li>中文：{dictionaries.zh.nav.tasks} / {dictionaries.zh.terms.schema}</li>
              <li>English：{dictionaries.en.nav.tasks} / {dictionaries.en.terms.schema}</li>
              <li>日期、数字、百分比、货币按 locale 格式化。</li>
            </ul>
          </div>
        </section>
        <section className="panel">
          <div className="panel-header">
            <strong>权限视图</strong>
          </div>
          <div className="panel-body">
            <ul className="evidence-list">
              <li>业务域权限控制可见数据源、表和字段。</li>
              <li>分享页仅对有权限成员可见。</li>
              <li>任务页展示本次分析使用的授权范围。</li>
            </ul>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
