import { AppShell } from "@/components/layout/app-shell";
import { AnalysisWorkbench } from "@/components/workbench/analysis-workbench";
import { sampleTask } from "@/lib/sample-task";

export default function TaskPage() {
  return (
    <AppShell active="/">
      <AnalysisWorkbench task={sampleTask} />
    </AppShell>
  );
}
