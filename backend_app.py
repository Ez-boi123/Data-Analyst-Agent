from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.charts import build_chart
from agent.data_source import (
    DataCatalog,
    connection_from_catalog,
    load_default_sample,
    load_sqlalchemy_url,
)
from agent.langchain_agent import ConversationTurn, LangChainDataAgent
from agent.schema import SchemaProfile, profile_tables
from agent.sql_agent import AgentRun


WORKDIR = Path(__file__).parent
DEFAULT_DOMAIN = "经营分析"
DEFAULT_PERMISSIONS = "demo: 只读沙箱，可访问样例经营分析数据域"
DEFAULT_OWNER = "Data Analyst Agent"
SQL_SAFETY_STATUS = ["只读 SELECT", "行数限制 500", "超时 30s", "业务域权限过滤"]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(WORKDIR / ".env")


class CreateTaskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    title: str | None = None
    businessDomain: str = DEFAULT_DOMAIN
    dataSourceUrl: str | None = None
    parentTaskId: str | None = None


class FollowUpRequest(BaseModel):
    message: str = Field(..., min_length=1)


@dataclass
class ChatMessage:
    role: str
    content: str
    createdAt: float = field(default_factory=time.time)


@dataclass
class StoredTask:
    id: str
    title: str
    question: str
    businessDomain: str
    dataSourceUrl: str | None
    status: str = "clarifying"
    createdBy: str = "demo-user"
    createdAt: float = field(default_factory=time.time)
    updatedAt: float = field(default_factory=time.time)
    parentTaskId: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    messages: list[ChatMessage] = field(default_factory=list)
    branches: list[dict[str, str]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    shareState: str = "private"
    lastRun: AgentRun | None = None
    lastError: str = ""


TASKS: dict[str, StoredTask] = {}
CATALOG_CACHE: dict[str, tuple[DataCatalog, SchemaProfile]] = {}


app = FastAPI(title="Data Analyst Agent Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    agent = LangChainDataAgent()
    return {
        "ok": True,
        "agent": "langchain",
        "model": agent.model,
        "configured": agent.is_configured,
        "unavailableReason": agent.unavailable_reason,
    }


@app.get("/api/data-sources/default/schema")
def default_schema() -> dict[str, Any]:
    catalog, schema = get_catalog_and_schema(None)
    return {
        "sourceLabel": catalog.source_label,
        "rowCount": catalog.row_count,
        "tables": [table_to_view(table) for table in schema.tables],
        "joinPaths": [relation_to_view(relation) for relation in schema.relations],
    }


@app.get("/api/data-sources")
def data_sources() -> dict[str, Any]:
    catalog, schema = get_catalog_and_schema(None)
    return {
        "items": [
            {
                "id": "default",
                "name": catalog.source_label,
                "domain": DEFAULT_DOMAIN,
                "status": "synced",
                "tables": len(catalog.tables),
                "fields": sum(len(table.columns) for table in schema.tables),
                "lastSync": iso_now(),
            }
        ]
    }


@app.get("/api/glossary")
def glossary() -> dict[str, Any]:
    return {"items": glossary_items()}


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    tasks = sorted(TASKS.values(), key=lambda item: item.updatedAt, reverse=True)
    return {"items": [task_to_view(task, compact=True) for task in tasks]}


@app.post("/api/tasks")
def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    task_id = new_id("task")
    title = request.title.strip() if request.title and request.title.strip() != request.question[:32] else generate_task_title(request.question)
    task = StoredTask(
        id=task_id,
        title=title,
        question=request.question,
        businessDomain=request.businessDomain,
        dataSourceUrl=request.dataSourceUrl,
        parentTaskId=request.parentTaskId,
        messages=[ChatMessage(role="user", content=request.question)],
    )
    task.steps.append(initial_clarifying_step(request))
    TASKS[task_id] = task
    if request.parentTaskId and request.parentTaskId in TASKS:
        TASKS[request.parentTaskId].branches.append(
            {
                "id": task_id,
                "title": title,
                "summary": request.question,
                "delta": "基于原任务创建的追问分支",
            }
        )
    return task_to_view(task)


def generate_task_title(question: str) -> str:
    agent = LangChainDataAgent()
    if agent.is_configured:
        try:
            title = clean_task_title(agent.title_generation_tool(question))
            if title:
                return title
        except Exception:
            pass
    return fallback_task_title(question)


def clean_task_title(value: str) -> str:
    title = str(value or "").strip()
    title = title.strip("`\"'“”‘’《》<>：:，,。.!！?？#* ")
    for prefix in ["标题", "任务标题", "分析标题"]:
        if title.startswith(prefix):
            title = title[len(prefix) :].strip("：: ")
    title = title.replace("\n", " ").strip()
    if len(title) > 24:
        title = title[:24].rstrip()
    return title


def fallback_task_title(question: str) -> str:
    lowered = question.lower()
    if any(token in question for token in ["年龄", "性别", "分层"]) or any(token in lowered for token in ["age", "gender", "segment"]):
        return "用户分层购买分析"
    if any(token in question for token in ["曝光", "点击", "转化", "漏斗"]) or any(
        token in lowered for token in ["exposure", "click", "conversion", "funnel"]
    ):
        return "转化漏斗分析"
    if any(token in question for token in ["品类", "商品", "偏好"]) or any(token in lowered for token in ["category", "product"]):
        return "品类偏好分析"
    if any(token in question for token in ["支付", "客单价", "销售额", "订单"]) or any(
        token in lowered for token in ["payment", "aov", "sales", "order"]
    ):
        return "交易行为分析"
    return "经营数据智能分析"


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    return task_to_view(require_task(task_id))


@app.post("/api/tasks/{task_id}/messages")
def add_follow_up(task_id: str, request: FollowUpRequest) -> dict[str, Any]:
    task = require_task(task_id)
    task.messages.append(ChatMessage(role="user", content=request.message))
    task.updatedAt = time.time()
    return task_to_view(task)


@app.get("/api/tasks/{task_id}/stream")
def stream_task_get(task_id: str, message: str | None = None) -> StreamingResponse:
    return stream_task(task_id, message)


@app.post("/api/tasks/{task_id}/runs/stream")
def stream_task_post(task_id: str, request: FollowUpRequest | None = None) -> StreamingResponse:
    return stream_task(task_id, request.message if request else None)


def stream_task(task_id: str, message: str | None) -> StreamingResponse:
    task = require_task(task_id)
    if message:
        task.messages.append(ChatMessage(role="user", content=message))
        task.updatedAt = time.time()
    question = latest_user_message(task)

    return StreamingResponse(
        stream_agent_events(task, question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def stream_agent_events(task: StoredTask, question: str) -> Iterator[str]:
    try:
        catalog, schema = get_catalog_and_schema(task.dataSourceUrl)
        connection = connection_from_catalog(catalog)
        agent = LangChainDataAgent(max_rows=500)
        if not agent.is_configured:
            raise RuntimeError(agent.unavailable_reason or "LangChain Agent 未配置")

        task.status = "understanding"
        task.updatedAt = time.time()
        yield sse("task", task_to_view(task, compact=True))

        history = task_history(task)
        for event in agent.stream(question, schema, connection, history=history):
            if event.event_type == "step":
                step = upsert_step(task, event, schema)
                task.status = map_step_status(step["type"], step["status"])
                task.updatedAt = time.time()
                yield sse("step", step)
            elif event.event_type == "token":
                yield sse("token", {"stepType": "insight_generation", "content": event.message})
            elif event.event_type == "final" and event.run is not None:
                task.lastRun = event.run
                task.status = "completed"
                task.updatedAt = time.time()
                task.messages.append(ChatMessage(role="assistant", content=event.run.analysis))
                apply_final_details(task, event.run, schema)
                yield sse("result", result_view(event.run))
                yield sse("task", task_to_view(task))
                yield sse("done", {"taskId": task.id, "status": task.status})
    except Exception as exc:
        task.status = "failed_recoverable"
        task.lastError = str(exc)
        task.updatedAt = time.time()
        task.steps.append(error_step(str(exc)))
        yield sse("error", {"taskId": task.id, "status": task.status, "message": str(exc), "recoverable": True})


def get_catalog_and_schema(data_source_url: str | None) -> tuple[DataCatalog, SchemaProfile]:
    url = data_source_url or os.getenv("DATA_SOURCE_URL") or os.getenv("DEMO_DATABASE_URL") or ""
    cache_key = url or "__default__"
    if cache_key not in CATALOG_CACHE:
        catalog = load_sqlalchemy_url(url) if url else load_default_sample(WORKDIR)
        CATALOG_CACHE[cache_key] = (catalog, profile_tables(catalog.tables))
    return CATALOG_CACHE[cache_key]


def require_task(task_id: str) -> StoredTask:
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return TASKS[task_id]


def latest_user_message(task: StoredTask) -> str:
    for message in reversed(task.messages):
        if message.role == "user":
            return message.content
    return task.question


def task_history(task: StoredTask) -> list[ConversationTurn]:
    turns: list[ConversationTurn] = []
    if task.lastRun:
        turns.append(
            ConversationTurn(
                question=task.lastRun.question,
                sql=task.lastRun.final_sql,
                analysis=task.lastRun.analysis,
            )
        )
    return turns


def upsert_step(task: StoredTask, event: Any, schema: SchemaProfile) -> dict[str, Any]:
    step_type = step_name_to_type(event.name)
    now = time.time()
    existing = next((step for step in task.steps if step["type"] == step_type and step["status"] == "running"), None)
    if existing is None:
        existing = {
            "id": new_id("step"),
            "type": step_type,
            "status": step_status(event.status),
            "title": event.name,
            "summary": event.message,
            "evidence": step_evidence(step_type, event.message),
            "confidence": default_confidence(step_type),
            "startedAt": iso_timestamp(now),
            "finishedAt": None,
            "details": {},
        }
        task.steps.append(existing)
    existing["status"] = step_status(event.status)
    existing["summary"] = event.message
    if event.status in {"completed", "failed"}:
        existing["finishedAt"] = iso_timestamp(now)
    existing["evidence"] = step_evidence(step_type, event.message)
    if step_type in {"schema_retrieval", "relation_reasoning"}:
        existing["details"]["schema"] = schema_evidence_view(schema)
    if event.sql:
        existing["details"]["sql"] = sql_execution_view(sql=event.sql)
    if event.error:
        existing["details"]["sql"] = {
            **existing["details"].get("sql", sql_execution_view(sql=event.sql)),
            "executionStatus": "failed",
            "errorSummary": event.error,
        }
    return existing


def task_to_view(task: StoredTask, compact: bool = False) -> dict[str, Any]:
    view = {
        "id": task.id,
        "title": task.title,
        "question": task.question,
        "status": task.status,
        "businessDomain": task.businessDomain,
        "createdBy": task.createdBy,
        "createdAt": iso_timestamp(task.createdAt),
        "updatedAt": iso_timestamp(task.updatedAt),
        "permissionsSummary": DEFAULT_PERMISSIONS,
        "steps": [normalize_step(step) for step in task.steps],
        "branches": task.branches,
        "comments": normalize_comments(task.comments),
        "shareState": task.shareState,
        "audit": audit_view(task),
        "messages": [asdict(message) for message in task.messages],
        "parentTaskId": task.parentTaskId,
    }
    if task.lastRun and not compact:
        view["result"] = result_view(task.lastRun)
    if task.lastError:
        view["error"] = {"message": task.lastError, "recoverable": True}
    return view


def result_view(run: AgentRun) -> dict[str, Any]:
    chart = build_chart(run.result, run.chart_config or run.chart_instruction)
    return {
        "sqlExecution": sql_execution_view(run=run),
        "resultTable": dataframe_preview(run.result),
        "insight": insight_view(run, chart.chart_type),
        "analysis": run.analysis,
        "chartInstruction": run.chart_instruction,
    }


def dataframe_preview(frame: pd.DataFrame, limit: int = 100) -> dict[str, Any]:
    preview = frame.head(limit).copy()
    return {
        "rowCount": len(frame),
        "previewRowCount": len(preview),
        "columns": [{"key": str(column), "type": str(frame[column].dtype)} for column in frame.columns],
        "rows": json.loads(preview.to_json(orient="records", date_format="iso", force_ascii=False)),
        "limit": limit,
    }


def apply_final_details(task: StoredTask, run: AgentRun, schema: SchemaProfile) -> None:
    result_rows = compatible_result_rows(run.result)
    schema_view = schema_evidence_view(schema)
    sql_view = sql_execution_view(run=run)
    insight = insight_view(run)

    sql_step = ensure_step(task, "sql_generation", "生成只读 SQL")
    sql_step["status"] = "completed"
    sql_step["summary"] = "生成 SELECT 查询，默认限行 500，超时 30 秒。"
    sql_step["evidence"] = ["只读沙箱", "字段按 Schema 校验", "行数限制 500"]
    sql_step["details"]["sql"] = sql_view

    execution_step = ensure_step(task, "sql_execution", "执行 SQL 并预览结果")
    execution_step["status"] = "completed"
    execution_step["summary"] = f"SQL 执行成功，返回 {len(run.result):,} 行，前端展示分页预览。"
    execution_step["evidence"] = [f"返回 {len(run.result):,} 行", "结果表支持分页预览", "查询仅在只读沙箱执行"]
    execution_step["details"]["sql"] = sql_view
    execution_step["details"]["resultRows"] = result_rows

    if run.repair_steps:
        repair_step = ensure_step(task, "sql_repairing", "SQL 错误自修复")
        repair_step["status"] = "completed"
        repair_step["summary"] = "SQL 执行失败后，Agent 根据错误信息与 Schema 自动修复并重试成功。"
        repair_step["evidence"] = ["捕获执行错误", "使用 Schema 约束修复 SQL", "重试成功"]
        repair_step["details"]["sql"] = sql_view

    insight_step = ensure_step(task, "insight_generation", "生成图表、结论和建议")
    insight_step["status"] = "completed"
    insight_step["summary"] = first_line(run.analysis)
    insight_step["evidence"] = insight["evidence"]
    insight_step["details"]["insight"] = insight
    insight_step["details"]["resultRows"] = result_rows

    schema_step = ensure_step(task, "schema_retrieval", "检索相关 Schema")
    schema_step["details"]["schema"] = schema_view
    relation_step = ensure_step(task, "relation_reasoning", "推理表关联路径")
    relation_step["details"]["schema"] = schema_view


def ensure_step(task: StoredTask, step_type: str, title: str) -> dict[str, Any]:
    existing = next((step for step in task.steps if step["type"] == step_type), None)
    if existing is not None:
        return existing
    step = {
        "id": new_id("step"),
        "type": step_type,
        "status": "completed",
        "title": title,
        "summary": "",
        "evidence": [],
        "confidence": default_confidence(step_type),
        "startedAt": iso_now(),
        "finishedAt": iso_now(),
        "details": {},
    }
    task.steps.append(step)
    return step


def initial_clarifying_step(request: CreateTaskRequest) -> dict[str, Any]:
    return {
        "id": new_id("step"),
        "type": "clarifying",
        "status": "completed",
        "title": "确认分析任务",
        "summary": "已接收用户问题，使用默认只读沙箱和经营分析业务域继续分析。",
        "evidence": [
            f"业务域：{request.businessDomain}",
            "SQL：只允许 SELECT / WITH",
            "结果：默认限行 500",
        ],
        "confidence": 0.9,
        "startedAt": iso_now(),
        "finishedAt": iso_now(),
        "details": {
            "schema": {
                "tables": [],
                "fields": [],
                "joinPaths": [],
                "metricDefinitions": glossary_items(),
                "filters": ["默认只读沙箱", "默认行数限制 500"],
                "assumptions": ["使用当前默认数据源", "不展示模型原始思维链，只展示可验证证据"],
            }
        },
    }


def error_step(message: str) -> dict[str, Any]:
    return {
        "id": new_id("step"),
        "type": "failed_recoverable",
        "status": "failed_recoverable",
        "title": "可恢复失败",
        "summary": message,
        "evidence": [message],
        "confidence": 0.5,
        "startedAt": iso_now(),
        "finishedAt": iso_now(),
        "details": {"recoveryActions": ["检查模型配置", "补充数据源配置", "修改问题后重试"]},
    }


def normalize_step(step: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(step)
    normalized["status"] = step_status(str(normalized.get("status", "completed")))
    normalized["evidence"] = [str(item) for item in normalized.get("evidence", [])]
    normalized["details"] = normalized.get("details") or {}
    return normalized


def sql_execution_view(run: AgentRun | None = None, sql: str = "", error: str = "") -> dict[str, Any]:
    repair_steps = run.repair_steps if run else []
    return {
        "sql": run.final_sql if run else sql,
        "safetyStatus": SQL_SAFETY_STATUS,
        "rowLimit": 500,
        "timeoutMs": 30000,
        "executionStatus": "success" if run and not error else ("failed" if error else "pending"),
        "errorSummary": error or "",
        "repairAttempts": repair_attempts_view(repair_steps),
        "sqlDiff": "",
        "durationMs": 0,
    }


def repair_attempts_view(repair_steps: list[Any]) -> list[dict[str, Any]]:
    attempts = [
        {
            "attempt": item.attempt,
            "summary": f"执行失败：{item.error}",
            "status": "failed",
        }
        for item in repair_steps
    ]
    if attempts:
        attempts.append({"attempt": len(attempts) + 1, "summary": "修复 SQL 后重新执行成功", "status": "success"})
    return attempts


def schema_evidence_view(schema: SchemaProfile) -> dict[str, Any]:
    return {
        "tables": [
            {
                "id": table.name,
                "name": table.name,
                "domain": domain_for_table(table.name),
                "reason": f"包含 {table.row_count:,} 行、{len(table.columns)} 个字段，可支撑当前分析。",
                "confidence": 0.9,
                "fields": [
                    {
                        "name": column.name,
                        "type": column.sqlite_type,
                        "sensitive": any(token in column.name.lower() for token in ["user", "customer", "phone", "email"]),
                    }
                    for column in table.columns[:12]
                ],
            }
            for table in schema.tables[:8]
        ],
        "fields": [f"{table.name}.{column.name}" for table in schema.tables for column in table.columns[:8]][:40],
        "joinPaths": [
            {
                "from": f"{relation.left_table}.{relation.left_column}",
                "to": f"{relation.right_table}.{relation.right_column}",
                "condition": f"{relation.left_table}.{relation.left_column} = {relation.right_table}.{relation.right_column}",
                "confidence": 0.82,
            }
            for relation in schema.relations[:12]
        ],
        "metricDefinitions": glossary_items(),
        "filters": ["只读查询", "默认行数限制 500", "按用户问题自动生成筛选条件"],
        "assumptions": ["优先使用高置信度 Join Path", "指标口径以业务词典和字段画像为准"],
    }


def insight_view(run: AgentRun, chart_type: str | None = None) -> dict[str, Any]:
    frame = run.result
    chart_config = run.chart_config or {}
    normalized_chart_type = normalize_chart_type(chart_type or chart_config.get("chart_type"))
    categories, series = chart_series(frame, chart_config)
    analysis_lines = [line.strip(" -*#") for line in run.analysis.splitlines() if line.strip(" -*#")]
    return {
        "chartType": normalized_chart_type,
        "chartConfig": {
            "title": chart_config.get("reason") or "Agent 自动生成图表",
            "categories": categories,
            "series": series,
        },
        "headline": first_line(run.analysis),
        "evidence": analysis_lines[:3] or ["SQL 查询已完成，结果可用于进一步分析。"],
        "possibleCauses": analysis_lines[3:5],
        "recommendedNextSteps": default_next_steps(),
    }


def chart_series(frame: pd.DataFrame, config: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    if frame.empty:
        return [], [{"name": "结果", "data": []}]
    columns = [str(column) for column in frame.columns]
    numeric_columns = [str(column) for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    x_column = str(config.get("x") or "")
    if x_column not in columns:
        x_column = next((column for column in columns if column not in numeric_columns), columns[0])
    y_column = str(config.get("y") or "")
    y_columns = [y_column] if y_column in numeric_columns else numeric_columns[:3]
    if not y_columns:
        y_columns = [columns[-1]]
    preview = frame.head(20)
    categories = [safe_text(value) for value in preview[x_column].tolist()]
    series = []
    for column in y_columns:
        values = [safe_number(value) for value in preview[column].tolist()]
        series.append({"name": column, "data": values})
    return categories, series


def compatible_result_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    preview = frame.head(100).copy()
    return json.loads(preview.to_json(orient="records", date_format="iso", force_ascii=False))


def table_to_view(table: Any) -> dict[str, Any]:
    return {
        "name": table.name,
        "rowCount": table.row_count,
        "columns": [
            {
                "name": column.name,
                "type": column.sqlite_type,
                "semanticHint": column.semantic_hint,
                "nullRate": column.null_rate,
                "distinctCount": column.distinct_count,
                "samples": column.sample_values,
            }
            for column in table.columns
        ],
    }


def relation_to_view(relation: Any) -> dict[str, Any]:
    return {
        "from": {"table": relation.left_table, "field": relation.left_column},
        "to": {"table": relation.right_table, "field": relation.right_column},
        "confidence": 0.82,
        "reason": relation.reason,
    }


def step_name_to_type(name: str) -> str:
    mapping = {
        "Schema 理解": "schema_retrieval",
        "表关联推理": "relation_reasoning",
        "SQL 生成": "sql_generation",
        "SQL 执行": "sql_execution",
        "SQL 自修复": "sql_repairing",
        "图表建议": "insight_generation",
        "深度分析": "insight_generation",
    }
    return mapping.get(name, "understanding")


def map_step_status(step_type: str, status: str) -> str:
    if status in {"failed", "failed_recoverable"}:
        return "failed_recoverable"
    if status == "running":
        return step_type
    return step_type if step_type != "insight_generation" else "insight_generation"


def default_confidence(step_type: str) -> float:
    return 0.86 if step_type in {"schema_retrieval", "relation_reasoning"} else 0.78


def step_status(status: str) -> str:
    if status == "failed":
        return "failed_recoverable"
    if status in {"waiting", "running", "completed", "failed_recoverable"}:
        return status
    return "completed"


def step_evidence(step_type: str, message: str) -> list[str]:
    defaults = {
        "schema_retrieval": ["字段类型、样例值、缺失率已完成画像", "已提取相关表与候选字段"],
        "relation_reasoning": ["优先使用同名主外键字段", "Join Path 会在 SQL 生成时作为约束"],
        "sql_generation": ["只输出 SELECT / WITH", "默认限行并禁止写操作"],
        "sql_execution": ["只读沙箱执行", "执行失败会进入自修复"],
        "sql_repairing": ["保留原始错误", "结合 Schema 生成修复 SQL"],
        "insight_generation": ["基于查询结果生成结论", "不展示模型原始思维链"],
    }
    items = defaults.get(step_type, [])
    return [message, *items] if message else items


def audit_view(task: StoredTask) -> dict[str, Any]:
    repair_count = len(task.lastRun.repair_steps) if task.lastRun else 0
    return {
        "initiator": task.createdBy,
        "dataDomainsUsed": [task.businessDomain],
        "sqlGenerated": 1 if task.lastRun else 0,
        "sqlExecuted": 1 if task.lastRun else 0,
        "repairCount": repair_count,
        "sharedWith": [],
        "followUps": max(sum(1 for message in task.messages if message.role == "user") - 1, 0),
    }


def normalize_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for comment in comments:
        normalized.append(
            {
                "id": str(comment.get("id") or new_id("comment")),
                "author": str(comment.get("author") or "demo-user"),
                "body": str(comment.get("body") or ""),
                "createdAt": str(comment.get("createdAt") or iso_now()),
            }
        )
    return normalized


def first_line(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip(" -*#")
        if clean:
            return clean[:120]
    return "分析完成"


def glossary_items() -> list[dict[str, str]]:
    return [
        {
            "id": "order_count",
            "metric": "订单数",
            "definition": "按订单主键去重后的订单数量。",
            "owner": "交易数据组",
            "freshness": "Demo 数据随本地数据库同步",
        },
        {
            "id": "sales_amount",
            "metric": "销售额",
            "definition": "订单金额 order_amount 汇总，用于衡量交易规模。",
            "owner": "经营分析组",
            "freshness": "Demo 数据随本地数据库同步",
        },
        {
            "id": "avg_order_value",
            "metric": "客单价",
            "definition": "销售额 / 订单数，用于比较不同用户分层的消费水平。",
            "owner": "经营分析组",
            "freshness": "Demo 数据随本地数据库同步",
        },
        {
            "id": "funnel_rate",
            "metric": "转化率",
            "definition": "曝光、点击、购买链路中的阶段转化比例。",
            "owner": "增长分析组",
            "freshness": "Demo 数据随本地数据库同步",
        },
    ]


def domain_for_table(table_name: str) -> str:
    lowered = table_name.lower()
    if "customer" in lowered or "user" in lowered:
        return "用户域"
    if "product" in lowered or "category" in lowered:
        return "商品域"
    if "exposure" in lowered or "click" in lowered:
        return "流量域"
    if "order" in lowered or "payment" in lowered:
        return "交易域"
    return DEFAULT_DOMAIN


def normalize_chart_type(chart_type: Any) -> str:
    value = str(chart_type or "bar").lower()
    return value if value in {"line", "bar", "pie", "scatter", "bubble", "table"} else "bar"


def default_next_steps() -> list[str]:
    return ["继续按年龄段和性别拆解", "查看品类偏好差异", "分析曝光到点击再到购买的转化漏斗"]


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def safe_number(value: Any) -> float:
    if pd.isna(value):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def iso_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def iso_now() -> str:
    return iso_timestamp(time.time())


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
