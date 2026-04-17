import Link from "next/link";
import { BarChart3, BookOpen, Database, Settings, Sparkles } from "lucide-react";
import { getDictionary } from "@/lib/i18n";

const navItems = [
  { href: "/", label: "tasks", icon: BarChart3 },
  { href: "/data-sources", label: "dataSources", icon: Database },
  { href: "/glossary", label: "glossary", icon: BookOpen },
  { href: "/settings", label: "settings", icon: Settings }
] as const;

export function AppShell({ children, active = "/" }: { children: React.ReactNode; active?: string }) {
  const dict = getDictionary("zh");

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <Link className="brand-mark" href="/">
          <span className="brand-icon">DA</span>
          <span>
            <strong>Data Analyst Agent</strong>
            <br />
            <small>证据化智能分析</small>
          </span>
        </Link>
        <nav aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} className={`nav-link ${active === item.href ? "active" : ""}`} href={item.href}>
                <Icon size={17} />
                <span>{dict.nav[item.label]}</span>
              </Link>
            );
          })}
        </nav>
        <div className="panel sandbox-note">
          <div className="panel-body">
            <span className="status-pill">
              <Sparkles size={13} />
              只读沙箱
            </span>
            <p className="subtitle" style={{ marginBottom: 0 }}>
              SQL 仅允许 SELECT，默认限行、超时、脱敏和业务域权限过滤。
            </p>
          </div>
        </div>
      </aside>
      <main className="page">{children}</main>
    </div>
  );
}
