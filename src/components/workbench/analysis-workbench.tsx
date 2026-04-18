"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Check,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  GitBranch,
  Send,
  Share2,
  Sparkles,
  Table2
} from "lucide-react";
import type { AnalysisStep, AnalysisTask } from "@/lib/types";
import { getTaskAuditItems } from "@/lib/sample-task";
import { getTask, streamFollowUp, streamTaskRun, type AgentStreamEvent } from "@/lib/api";
import { SchemaGraph } from "./schema-graph";
import { ResultTable } from "./result-table";
import { InsightChart } from "./insight-chart";

const tabLabels = ["口径", "Schema", "SQL", "结果", "洞察", "审计"] as const;
type DetailTab = (typeof tabLabels)[number];

const analysisModels = [
  { id: "deep-analysis", label: "深度分析模型", description: "复杂归因与多表推理" },
  { id: "fast-sql", label: "快速 SQL 模型", description: "快速生成查询与预览" },
  { id: "schema-reasoning", label: "Schema 推理模型", description: "表关联与字段理解优先" }
] as const;

const sqlKeywords = new Set([
  "SELECT",
  "FROM",
  "WHERE",
  "JOIN",
  "LEFT",
  "RIGHT",
  "INNER",
  "OUTER",
  "ON",
  "AND",
  "OR",
  "GROUP",
  "BY",
  "ORDER",
  "LIMIT",
  "AS",
  "CASE",
  "WHEN",
  "THEN",
  "ELSE",
  "END",
  "WITH",
  "HAVING",
  "DESC",
  "ASC",
  "BETWEEN",
  "IN",
  "IS",
  "NULL",
  "NOT"
]);

const sqlFunctions = new Set(["SUM", "COUNT", "AVG", "MIN", "MAX", "ROUND", "COALESCE", "DATE_TRUNC"]);

export function AnalysisWorkbench({ initialTask, autoRun = false }: { initialTask: AnalysisTask; autoRun?: boolean }) {
  const [task, setTask] = useState(initialTask);
  const [isRunning, setIsRunning] = useState(false);
  const [streamingInsight, setStreamingInsight] = useState("");
  const [activeStepId, setActiveStepId] = useState("step-repair");
  const [activeTab, setActiveTab] = useState<DetailTab>("SQL");
  const [isChatExpanded, setIsChatExpanded] = useState(true);
  const autoRunStarted = useRef(false);
  const activeStep = useMemo(
    () => task.steps.find((step) => step.id === activeStepId) ?? task.steps[0],
    [activeStepId, task.steps]
  );

  useEffect(() => {
    setTask(initialTask);
  }, [initialTask]);

  useEffect(() => {
    if (!autoRun || autoRunStarted.current) return;
    const storageKey = `data-agent-run-${initialTask.id}`;
    if (typeof window !== "undefined" && window.sessionStorage.getItem(storageKey)) return;
    autoRunStarted.current = true;
    window.sessionStorage.setItem(storageKey, "1");
    window.history.replaceState(null, "", `/tasks/${initialTask.id}`);
    void runStream(() => streamTaskRun(initialTask.id, handleStreamEvent));
  }, [autoRun, initialTask.id]);

  async function runStream(streamer: () => Promise<void>) {
    setIsRunning(true);
    setStreamingInsight("");
    try {
      await streamer();
      const refreshed = await getTask(task.id);
      setTask(refreshed);
    } catch (error) {
      console.error(error);
    } finally {
      setIsRunning(false);
    }
  }

  function handleStreamEvent(event: AgentStreamEvent) {
    if (event.event === "task") {
      setTask(event.data);
    }
    if (event.event === "step") {
      setTask((current) => mergeStep(current, event.data));
      setActiveStepId(event.data.id);
      if (event.data.details.sql) setActiveTab("SQL");
      else if (event.data.details.schema) setActiveTab("Schema");
      else if (event.data.details.insight) setActiveTab("洞察");
    }
    if (event.event === "token") {
      setStreamingInsight((current) => current + event.data.content);
    }
    if (event.event === "error") {
      setTask((current) => ({
        ...current,
        status: "failed_recoverable",
        steps: [
          ...current.steps,
          {
            id: `client-error-${Date.now()}`,
            type: "failed_recoverable",
            status: "failed_recoverable",
            title: "可恢复失败",
            summary: event.data.message,
            evidence: [event.data.message],
            confidence: 0.5,
            details: { recoveryActions: ["检查后端服务", "检查模型配置", "修改问题后重试"] }
          }
        ]
      }));
    }
  }

  function handleFollowUp(message: string) {
    setTask((current) => ({
      ...current,
      messages: [...(current.messages ?? []), { role: "user", content: message, createdAt: new Date().toISOString() }]
    }));
    void runStream(() => streamFollowUp(task.id, message, handleStreamEvent));
  }

  if (!activeStep) {
    return <div className="panel"><div className="panel-body">任务初始化中...</div></div>;
  }

  return (
    <div className={`workspace ${isChatExpanded ? "" : "chat-collapsed"}`}>
      <aside className="chat-column">
        <div className="panel agent-chat-panel">
          <div className="panel-header agent-chat-header">
            <button
              aria-label={isChatExpanded ? "收起 Agent 对话栏" : "展开 Agent 对话栏"}
              className="chat-toggle"
              onClick={() => setIsChatExpanded((current) => !current)}
              type="button"
            >
              {isChatExpanded ? <ChevronsLeft size={16} /> : <ChevronsRight size={16} />}
            </button>
            <strong>Agent 对话</strong>
            <span className="status-pill">{isRunning ? "运行中" : task.status === "completed" ? "运行完成" : "等待执行"}</span>
          </div>
          <button
            aria-label="展开 Agent 对话栏"
            className="chat-collapsed-trigger"
            onClick={() => setIsChatExpanded(true)}
            type="button"
          >
            <ChevronsRight size={16} />
            <span>Agent对话</span>
          </button>
          <div className="panel-body">
            <div className="agent-chat-messages">
              {(task.messages?.length ? task.messages : [{ role: "user", content: task.question, createdAt: task.createdAt }]).map((message, index) => (
                <div className={`message ${message.role === "user" ? "user" : ""}`} key={`${message.createdAt}-${index}`}>
                  <strong>{message.role === "user" ? task.createdBy : "Data Analyst Agent"}</strong>
                  <p>{message.content}</p>
                </div>
              ))}
              {streamingInsight ? (
                <div className="message">
                  <strong>Data Analyst Agent</strong>
                  <p>{streamingInsight}</p>
                </div>
              ) : null}
              <div className="message">
                <strong>关键澄清</strong>
                <ul className="evidence-list">
                  <li>业务域：{task.businessDomain}</li>
                  <li>数据边界：只使用当前 Schema 中存在的表和字段</li>
                  <li>指标口径：以业务词典、SQL 和查询结果字段为准</li>
                </ul>
              </div>
            </div>
            <FollowUpComposer disabled={isRunning} onSubmit={handleFollowUp} />
          </div>
        </div>
      </aside>

      <section className="timeline-column">
        <div className="task-title-sticky">
          <div>
            <div className="eyebrow">{task.businessDomain}</div>
            <h1 className="title agent-title task-title">{task.title}</h1>
            <p className="subtitle">{task.question} · {task.permissionsSummary}</p>
          </div>
          <Link className="button" href={`/share/tasks/${task.id}`}>
            <Share2 size={16} />
            分享任务
          </Link>
        </div>
        <TaskSummary isRunning={isRunning} task={task} />
        <div className="panel">
          <div className="panel-header">
            <strong>证据时间线</strong>
            <Link className="button" href={`/share/tasks/${task.id}`}>
              打开分享页
              <ArrowRight size={16} />
            </Link>
          </div>
          <div className="panel-body">
            <div className="timeline">
              {task.steps.map((step) => (
                <TimelineStep
                  key={step.id}
                  step={step}
                  isActive={step.id === activeStep.id}
                  onSelect={() => {
                    setActiveStepId(step.id);
                    if (step.details.sql) setActiveTab("SQL");
                    else if (step.details.schema) setActiveTab("Schema");
                    else if (step.details.insight) setActiveTab("洞察");
                    else setActiveTab("口径");
                  }}
                />
              ))}
            </div>
            <StepDetails task={task} step={activeStep} activeTab={activeTab} onTabChange={setActiveTab} />
            <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-body">
                <ResultTable rows={task.steps.flatMap((item) => item.details.resultRows ?? []).slice(0, 7)} />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function mergeStep(task: AnalysisTask, step: AnalysisStep): AnalysisTask {
  const index = task.steps.findIndex((item) => item.id === step.id);
  const steps = index >= 0 ? [...task.steps] : [...task.steps, step];
  if (index >= 0) {
    steps[index] = step;
  }
  return {
    ...task,
    status: step.status === "failed_recoverable" ? "failed_recoverable" : step.type,
    steps
  };
}

function FollowUpComposer({ disabled, onSubmit }: { disabled: boolean; onSubmit: (message: string) => void }) {
  const [followUp, setFollowUp] = useState("");
  const [selectedModel, setSelectedModel] = useState<(typeof analysisModels)[number]>(analysisModels[0]);
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = followUp.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setFollowUp("");
  }

  return (
    <div className="prompt-launcher follow-up-launcher">
      <form className="prompt-composer" onSubmit={handleSubmit}>
        <input
          aria-label="输入追问"
          placeholder="继续追问，例如：广告渠道是否异常？"
          value={followUp}
          onChange={(event) => setFollowUp(event.target.value)}
        />
        <button aria-label="发送追问" className="prompt-send" data-empty={!followUp.trim() || disabled} disabled={disabled} type="submit">
          <Send size={16} />
        </button>
      </form>
      <div className="model-picker" onBlur={() => setIsModelPickerOpen(false)}>
        <span className="model-picker-label">模型</span>
        <button
          aria-expanded={isModelPickerOpen}
          aria-haspopup="listbox"
          className="model-picker-trigger"
          onClick={() => setIsModelPickerOpen((current) => !current)}
          type="button"
        >
          {selectedModel.label}
          <ChevronDown className="model-picker-chevron" size={14} />
        </button>
        {isModelPickerOpen ? (
          <div aria-label="选择追问模型" className="model-picker-menu" role="listbox">
            {analysisModels.map((model) => (
              <button
                aria-selected={model.id === selectedModel.id}
                className="model-option"
                key={model.id}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setSelectedModel(model);
                  setIsModelPickerOpen(false);
                }}
                role="option"
                type="button"
              >
                <span>
                  <strong>{model.label}</strong>
                  <small>{model.description}</small>
                </span>
                {model.id === selectedModel.id ? <Check size={15} /> : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TaskSummary({ task, isRunning }: { task: AnalysisTask; isRunning: boolean }) {
  return (
    <div className="metric-grid">
      <div className="metric">
        <div className="metric-top">
          <span className={`status-light ${task.status === "failed_recoverable" ? "danger" : "success"}`} aria-label={task.status} />
          <span className="subtitle">任务状态</span>
        </div>
        <strong>{isRunning ? "运行中" : task.status === "completed" ? "已完成" : task.status === "failed_recoverable" ? "可恢复" : "待执行"}</strong>
      </div>
      <div className="metric">
        <div className="metric-top">
          <Table2 size={17} />
          <span className="subtitle">Schema 置信度</span>
        </div>
        <strong>92%</strong>
      </div>
      <div className="metric">
        <div className="metric-top">
          <Sparkles size={17} />
          <span className="subtitle">SQL 自修复</span>
        </div>
        <strong>{task.audit.repairCount} 次</strong>
      </div>
      <div className="metric">
        <div className="metric-top">
          <GitBranch size={17} />
          <span className="subtitle">追问分支</span>
        </div>
        <strong>{task.branches.length} 个</strong>
      </div>
    </div>
  );
}

function TimelineStep({ step, isActive, onSelect }: { step: AnalysisStep; isActive: boolean; onSelect: () => void }) {
  return (
    <button className={`step ${isActive ? "active" : ""}`} type="button" onClick={onSelect}>
      <div className="step-top">
        <div style={{ textAlign: "left" }}>
          <strong className="timeline-step-title">{step.title}</strong>
          <p className="subtitle" style={{ margin: "6px 0 0" }}>
            {step.summary}
          </p>
        </div>
        <span className={`status-pill ${step.status === "failed_recoverable" ? "danger" : ""}`}>
          <CheckCircle2 size={13} />
          {step.status === "failed_recoverable" ? "可恢复" : "完成"}
        </span>
      </div>
      <ul className="evidence-list">
        {step.evidence.slice(0, 3).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </button>
  );
}

function StepDetails({
  task,
  step,
  activeTab,
  onTabChange
}: {
  task: AnalysisTask;
  step: AnalysisStep;
  activeTab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
}) {
  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <div className="panel-header">
        <strong>{step.title} · 详情</strong>
        <span className="status-pill">置信度 {Math.round(step.confidence * 100)}%</span>
      </div>
      <div className="panel-body">
        <div className="tabs" role="tablist" aria-label="阶段详情">
          {tabLabels.map((tab) => (
            <button key={tab} className={`tab ${activeTab === tab ? "active" : ""}`} type="button" onClick={() => onTabChange(tab)}>
              {tab}
            </button>
          ))}
        </div>
        {activeTab === "口径" && (
          <div className="two-col">
            <InfoList title="证据化解释" items={step.evidence} />
            <InfoList title="业务假设" items={step.details.schema?.assumptions ?? ["不展示原始模型思维链，只展示可验证证据。"]} />
          </div>
        )}
        {activeTab === "Schema" && step.details.schema && <SchemaGraph schema={step.details.schema} />}
        {activeTab === "SQL" && <SqlPanel step={step} />}
        {activeTab === "结果" && <ResultTable rows={step.details.resultRows ?? task.steps.flatMap((item) => item.details.resultRows ?? []).slice(0, 7)} />}
        {activeTab === "洞察" && <InsightSection step={step} />}
        {activeTab === "审计" && <InfoList title="任务级审计" items={getTaskAuditItems(task)} />}
      </div>
    </div>
  );
}

function SqlPanel({ step }: { step: AnalysisStep }) {
  const sql = step.details.sql;

  if (!sql) {
    return <p className="subtitle">当前阶段没有生成 SQL。</p>;
  }

  return (
    <div className="detail-grid sql-detail-grid">
      <div className="sql-code-panel">
        <h3 className="section-title">格式化 SQL</h3>
        <pre className="code-block sql-code-block"><HighlightedSql code={sql.sql} /></pre>
      </div>
      <div className="sql-summary-panel">
        <h3 className="section-title">修复摘要</h3>
        {sql.errorSummary ? <p>{sql.errorSummary}</p> : <p className="subtitle">SQL 已在只读沙箱中执行成功。</p>}
        <InfoList title="安全状态" items={sql.safetyStatus} />
        {sql.sqlDiff && (
          <>
            <h4 className="section-title small">SQL Diff</h4>
            <pre className="code-block sql-diff-block"><HighlightedSql code={sql.sqlDiff} /></pre>
          </>
        )}
        <InfoList title="重试历史" items={sql.repairAttempts.map((item) => `第 ${item.attempt} 次：${item.summary}（${item.status}）`)} />
      </div>
    </div>
  );
}

function HighlightedSql({ code }: { code: string }) {
  const tokens = code.split(/(\s+|--.*$|'[^']*'|"[^"]*"|\b\d+(?:\.\d+)?\b|[(),.=+\-*/<>])/gm);

  return (
    <>
      {tokens.map((token, index) => {
        if (!token) return null;
        const upperToken = token.toUpperCase();
        let className = "";

        if (/^--/.test(token)) className = "sql-comment";
        else if (/^['"]/.test(token)) className = "sql-string";
        else if (/^\d/.test(token)) className = "sql-number";
        else if (sqlKeywords.has(upperToken)) className = "sql-keyword";
        else if (sqlFunctions.has(upperToken)) className = "sql-function";
        else if (/^[(),.=+\-*/<>]$/.test(token)) className = "sql-operator";
        else if (token.includes(".")) className = "sql-identifier";

        return className ? (
          <span className={className} key={`${token}-${index}`}>
            {token}
          </span>
        ) : (
          token
        );
      })}
    </>
  );
}

function InsightSection({ step }: { step: AnalysisStep }) {
  const insight = step.details.insight;

  if (!insight) {
    return <p className="subtitle">当前阶段还没有生成图表洞察。</p>;
  }

  return (
    <div className="detail-grid">
      <InsightChart insight={insight} />
      <div>
        <h3 style={{ marginTop: 0 }}>{insight.headline}</h3>
        <InfoList title="关键证据" items={insight.evidence} />
        <InfoList title="可能原因" items={insight.possibleCauses} />
        <InfoList title="下一步建议" items={insight.recommendedNextSteps} />
      </div>
    </div>
  );
}

function InfoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="section-title">{title}</h3>
      <ul className="evidence-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
