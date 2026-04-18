import type { AnalysisStep, AnalysisTask, DataSource, GlossaryMetric } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

type TaskListResponse = { items: AnalysisTask[] };
type DataSourceListResponse = { items: DataSource[] };
type GlossaryListResponse = { items: GlossaryMetric[] };
export type AgentStreamEvent =
  | { event: "task"; data: AnalysisTask }
  | { event: "step"; data: AnalysisStep }
  | { event: "token"; data: { stepType: string; content: string } }
  | { event: "result"; data: unknown }
  | { event: "error"; data: { message: string; recoverable: boolean; status?: string } }
  | { event: "done"; data: { taskId: string; status: string } };

export async function createTask(question: string, model?: string): Promise<AnalysisTask> {
  const response = await apiFetch("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      question,
      businessDomain: model === "schema-reasoning" ? "经营分析 / Schema 推理" : "经营分析 / 交易域"
    })
  });
  return response.json();
}

export async function listTasks(): Promise<AnalysisTask[]> {
  const response = await apiFetch("/api/tasks", { cache: "no-store" });
  const payload = (await response.json()) as TaskListResponse;
  return payload.items;
}

export async function getTask(taskId: string): Promise<AnalysisTask> {
  const response = await apiFetch(`/api/tasks/${taskId}`, { cache: "no-store" });
  return response.json();
}

export async function listDataSources(): Promise<DataSource[]> {
  const response = await apiFetch("/api/data-sources", { cache: "no-store" });
  const payload = (await response.json()) as DataSourceListResponse;
  return payload.items;
}

export async function listGlossaryMetrics(): Promise<GlossaryMetric[]> {
  const response = await apiFetch("/api/glossary", { cache: "no-store" });
  const payload = (await response.json()) as GlossaryListResponse;
  return payload.items;
}

export async function streamTaskRun(taskId: string, onEvent: (event: AgentStreamEvent) => void): Promise<void> {
  await streamSse(`${API_BASE_URL}/api/tasks/${taskId}/stream`, undefined, onEvent);
}

export async function streamFollowUp(
  taskId: string,
  message: string,
  onEvent: (event: AgentStreamEvent) => void
): Promise<void> {
  await streamSse(
    `${API_BASE_URL}/api/tasks/${taskId}/runs/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    },
    onEvent
  );
}

async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
  });
  if (!response.ok) {
    throw new Error(`API ${path} failed with ${response.status}`);
  }
  return response;
}

async function streamSse(url: string, init: RequestInit | undefined, onEvent: (event: AgentStreamEvent) => void) {
  const response = await fetch(url, init);
  if (!response.ok || !response.body) {
    throw new Error(`SSE request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const parsed = parseSseChunk(chunk);
      if (parsed) onEvent(parsed);
    }
  }
}

function parseSseChunk(chunk: string): AgentStreamEvent | null {
  const eventLine = chunk.split("\n").find((line) => line.startsWith("event:"));
  const dataLine = chunk.split("\n").find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;
  const event = eventLine.replace("event:", "").trim() as AgentStreamEvent["event"];
  const data = JSON.parse(dataLine.replace("data:", "").trim());
  return { event, data } as AgentStreamEvent;
}
