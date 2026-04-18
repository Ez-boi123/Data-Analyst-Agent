import { AppShell } from "@/components/layout/app-shell";
import { AnalysisWorkbench } from "@/components/workbench/analysis-workbench";
import { sampleTask } from "@/lib/sample-task";
import { getTask } from "@/lib/api";

type TaskPageProps = {
  params: Promise<{ taskId: string }>;
  searchParams: Promise<{ run?: string; offline?: string }>;
};

export default async function TaskPage({ params, searchParams }: TaskPageProps) {
  const { taskId } = await params;
  const query = await searchParams;
  const task = query.offline ? sampleTask : await getTask(taskId).catch(() => sampleTask);

  return (
    <AppShell active="/">
      <AnalysisWorkbench autoRun={query.run === "1" && task.id !== sampleTask.id} initialTask={task} />
    </AppShell>
  );
}
