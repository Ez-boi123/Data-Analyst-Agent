from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterator

import pandas as pd

from .schema import SchemaProfile
from .sql_agent import (
    AgentRun,
    AgentStep,
    RepairStep,
    add_limit,
    normalize_sql,
    sql_system_prompt,
    unavailable_concept_sql,
    validate_read_only_sql,
)

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    LANGCHAIN_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised when optional deps are absent.
    HumanMessage = None
    SystemMessage = None
    ChatOpenAI = None
    LANGCHAIN_IMPORT_ERROR = exc


@dataclass
class LangChainStreamEvent:
    event_type: str
    name: str = ""
    status: str = ""
    message: str = ""
    sql: str = ""
    error: str = ""
    run: AgentRun | None = None


@dataclass
class ConversationTurn:
    question: str
    sql: str = ""
    analysis: str = ""


class LangChainDataAgent:
    """A tool-style LangChain data analysis Agent with deterministic SQL safety rails."""

    tool_names = [
        "schema_understanding_tool",
        "relationship_reasoning_tool",
        "sql_generation_tool",
        "sql_execution_tool",
        "sql_repair_tool",
        "chart_recommendation_tool",
        "deep_analysis_tool",
    ]

    def __init__(self, max_rows: int = 500):
        self.base_url = os.getenv("LLM_BASE_URL") or None
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.max_rows = max_rows

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model and ChatOpenAI is not None)

    @property
    def unavailable_reason(self) -> str:
        if LANGCHAIN_IMPORT_ERROR:
            return f"LangChain 依赖不可用：{LANGCHAIN_IMPORT_ERROR}"
        if not self.api_key:
            return "未配置 LLM_API_KEY 或 OPENAI_API_KEY。"
        if not self.model:
            return "未配置 LLM_MODEL。"
        return ""

    def stream(
        self,
        question: str,
        schema: SchemaProfile,
        connection: sqlite3.Connection,
        history: list[ConversationTurn] | None = None,
    ) -> Iterator[LangChainStreamEvent]:
        if not self.is_configured:
            raise RuntimeError(self.unavailable_reason or "LangChain Agent 未配置。")

        steps: list[AgentStep] = []
        repair_steps: list[RepairStep] = []
        result = pd.DataFrame()
        final_sql = ""
        chart_config: dict[str, Any] | None = None
        chart_instruction = ""

        history = history or []
        standalone_question = self.rephrase_question_tool(question, history) if history else question

        schema_summary = self.schema_understanding_tool(schema)
        yield from self._complete_step(steps, "Schema 理解", schema_summary)

        relation_summary = self.relationship_reasoning_tool(schema)
        yield from self._complete_step(steps, "表关联推理", relation_summary)

        yield LangChainStreamEvent("step", "SQL 生成", "running", "正在基于 Schema 和关联路径生成只读 SQL...")
        final_sql = unavailable_concept_sql(standalone_question, schema)
        if final_sql:
            message = "用户问题涉及当前 Schema 不存在的指标或维度，已生成 Schema 说明查询。"
        else:
            final_sql = self.sql_generation_tool(standalone_question, schema, relation_summary, history)
            message = "已生成候选 SQL。"
        steps.append(AgentStep("SQL 生成", "completed", message, sql=final_sql))
        yield LangChainStreamEvent("step", "SQL 生成", "completed", message, sql=final_sql)

        for attempt in range(3):
            yield LangChainStreamEvent("step", "SQL 执行", "running", f"正在执行第 {attempt + 1} 次 SQL...")
            try:
                result = self.sql_execution_tool(connection, final_sql)
                steps.append(AgentStep("SQL 执行", "completed", f"SQL 执行成功，返回 {len(result):,} 行。", sql=final_sql))
                yield LangChainStreamEvent("step", "SQL 执行", "completed", f"SQL 执行成功，返回 {len(result):,} 行。", sql=final_sql)
                break
            except Exception as exc:
                error = str(exc)
                repair_steps.append(RepairStep(attempt=attempt + 1, sql=final_sql, error=error))
                steps.append(AgentStep("SQL 执行", "failed", "SQL 执行失败，进入自修复。", sql=final_sql, error=error))
                yield LangChainStreamEvent("step", "SQL 执行", "failed", "SQL 执行失败，进入自修复。", sql=final_sql, error=error)
                if attempt >= 2:
                    raise
                yield LangChainStreamEvent("step", "SQL 自修复", "running", "正在根据错误信息修复 SQL...")
                final_sql = self.sql_repair_tool(standalone_question, schema, final_sql, error, history)
                steps.append(AgentStep("SQL 自修复", "completed", "已生成修复后的 SQL。", sql=final_sql))
                yield LangChainStreamEvent("step", "SQL 自修复", "completed", "已生成修复后的 SQL。", sql=final_sql)

        yield LangChainStreamEvent("step", "图表建议", "running", "正在生成结构化图表建议...")
        chart_config = self.chart_recommendation_tool(standalone_question, final_sql, result)
        chart_instruction = str(chart_config.get("reason", "根据查询结果自动选择图表。"))
        steps.append(AgentStep("图表建议", "completed", chart_instruction))
        yield LangChainStreamEvent("step", "图表建议", "completed", chart_instruction)

        yield LangChainStreamEvent("step", "深度分析", "running", "正在流式生成业务分析结论...")
        analysis_chunks: list[str] = []
        for token in self.deep_analysis_tool(standalone_question, final_sql, result, schema, history):
            analysis_chunks.append(token)
            yield LangChainStreamEvent("token", "深度分析", "running", token)
        analysis = "".join(analysis_chunks).strip()
        steps.append(AgentStep("深度分析", "completed", "业务分析结论生成完成。"))
        yield LangChainStreamEvent("step", "深度分析", "completed", "业务分析结论生成完成。")

        run = AgentRun(
            question=standalone_question,
            final_sql=final_sql,
            result=result,
            analysis=analysis,
            chart_instruction=chart_instruction,
            repair_steps=repair_steps,
            steps=steps,
            chart_config=chart_config,
        )
        yield LangChainStreamEvent("final", run=run)

    def rephrase_question_tool(self, question: str, history: list[ConversationTurn]) -> str:
        context = format_history(history)
        messages = self._messages(
            "你是数据分析 Agent 的问题改写器。请把用户追问改写成可独立理解的问题，只输出改写后的问题。",
            (
                f"历史对话：\n{context}\n\n"
                f"用户最新追问：{question}\n\n"
                "如果最新问题已经完整，原样返回；如果有“继续、这些、它、上面”等指代，请结合历史补全。"
            ),
        )
        return self._invoke_text(messages, temperature=0.1).strip() or question

    def title_generation_tool(self, question: str) -> str:
        messages = self._messages(
            (
                "你是数据分析 Agent 的任务标题生成器。"
                "请根据用户问题生成一个中文短标题，体现分析对象、维度和指标。"
                "不要照抄用户原句，不要使用问号、句号、引号或 Markdown。"
                "标题长度控制在 6 到 18 个汉字。只输出标题。"
            ),
            (
                f"用户问题：{question}\n\n"
                "示例：\n"
                "问题：按年龄段和性别统计订单数、销售额、客单价。\n"
                "标题：用户分层购买分析\n"
                "问题：不同年龄和性别用户从曝光到点击再到购买的转化率是多少？\n"
                "标题：分层转化漏斗分析\n"
                "问题：哪些品类高曝光高点击但购买转化低？\n"
                "标题：品类流量转化诊断"
            ),
        )
        return self._invoke_text(messages, temperature=0.2).strip()

    def schema_understanding_tool(self, schema: SchemaProfile) -> str:
        table_count = len(schema.tables)
        column_count = sum(len(table.columns) for table in schema.tables)
        table_bits = [f"{table.name}({table.row_count:,}行/{len(table.columns)}列)" for table in schema.tables[:8]]
        return f"识别到 {table_count} 张表、{column_count} 个字段：" + "，".join(table_bits)

    def relationship_reasoning_tool(self, schema: SchemaProfile) -> str:
        if not schema.relations:
            return "未发现高置信度关联字段，后续 SQL 将优先使用单表或模型可推断的字段。"
        lines = [
            f"{item.left_table}.{item.left_column} -> {item.right_table}.{item.right_column}"
            for item in schema.relations[:10]
        ]
        return "可用关联路径：" + "；".join(lines)

    def sql_generation_tool(
        self,
        question: str,
        schema: SchemaProfile,
        relation_summary: str,
        history: list[ConversationTurn] | None = None,
    ) -> str:
        history_context = format_history(history or [])
        messages = self._messages(
            sql_system_prompt(),
            (
                "请基于下面的 schema 和关联路径生成 SQLite 兼容 SQL。\n\n"
                f"多轮历史上下文:\n{history_context}\n\n"
                f"Schema:\n{schema.to_llm_context()}\n\n"
                f"关联路径:\n{relation_summary}\n\n"
                f"用户问题：{question}\n\n"
                "只输出 SQL，不要解释，不要 Markdown。"
            ),
        )
        return normalize_sql(self._invoke_text(messages, temperature=0.1))

    def sql_execution_tool(self, connection: sqlite3.Connection, sql: str) -> pd.DataFrame:
        clean_sql = normalize_sql(sql)
        validate_read_only_sql(clean_sql)
        return pd.read_sql_query(add_limit(clean_sql, self.max_rows), connection)

    def sql_repair_tool(
        self,
        question: str,
        schema: SchemaProfile,
        sql: str,
        error: str,
        history: list[ConversationTurn] | None = None,
    ) -> str:
        history_context = format_history(history or [])
        messages = self._messages(
            sql_system_prompt(),
            (
                "下面 SQL 执行失败，请修复为可执行的 SQLite 兼容只读 SQL。\n\n"
                f"多轮历史上下文:\n{history_context}\n\n"
                f"Schema:\n{schema.to_llm_context()}\n\n"
                f"用户问题：{question}\n\n"
                f"失败 SQL:\n{sql}\n\n"
                f"错误信息:\n{error}\n\n"
                "只输出修复后的 SQL，不要解释，不要 Markdown。"
            ),
        )
        return normalize_sql(self._invoke_text(messages, temperature=0.1))

    def chart_recommendation_tool(self, question: str, sql: str, result: pd.DataFrame) -> dict[str, Any]:
        preview = result.head(30).to_csv(index=False)
        columns = ", ".join(map(str, result.columns))
        messages = self._messages(
            "你是数据可视化专家。必须只输出 JSON，不要 Markdown。",
            (
                f"用户问题：{question}\n\nSQL:\n{sql}\n\n结果字段：{columns}\n\n结果预览：\n{preview}\n\n"
                "请输出 JSON："
                '{"chart_type":"bar|line|pie|scatter|bubble|table","x":"字段名或空","y":"字段名或空",'
                '"size":"字段名或空","color":"字段名或空","reason":"中文推荐理由"}。'
                "字段名必须来自结果字段；如果不能画图，用 chart_type=table。"
            ),
        )
        raw = self._invoke_text(messages, temperature=0.2)
        return self._parse_chart_config(raw, result)

    def deep_analysis_tool(
        self,
        question: str,
        sql: str,
        result: pd.DataFrame,
        schema: SchemaProfile,
        history: list[ConversationTurn] | None = None,
    ) -> Iterator[str]:
        preview = result.head(40).to_csv(index=False)
        history_context = format_history(history or [])
        result_columns = ", ".join(map(str, result.columns))
        schema_columns = ", ".join(
            f"{table.name}.{column.name}"
            for table in schema.tables
            for column in table.columns
        )
        messages = self._messages(
            (
                "你是资深数据分析 Agent。请用中文输出比赛 demo 风格的业务分析，"
                "强调数据发现、分层差异、可能原因和下一步建议。"
                "必须遵守事实边界：只能基于 SQL、结果字段、结果预览和 Schema 字段解释；"
                "不要提及结果或 Schema 中不存在的指标、维度、表名或业务事实。"
                "如果 SQL 结果是 schema_notice，必须直接说明该问题当前数据无法回答，并给出可替代的问题。"
                "没有 refund/return 字段时不要讨论退款；没有具体城市字段时不要讨论用户所在城市。"
            ),
            (
                f"多轮历史上下文:\n{history_context}\n\n"
                f"用户问题：{question}\n\nSQL:\n{sql}\n\n"
                f"结果字段：{result_columns}\n\n"
                f"Schema 字段：{schema_columns}\n\n"
                f"结果预览：\n{preview}\n\n"
                "请输出 3-5 条要点，避免复述 SQL。"
            ),
        )
        yield from self._stream_text(messages, temperature=0.3)

    def _complete_step(self, steps: list[AgentStep], name: str, summary: str) -> Iterator[LangChainStreamEvent]:
        yield LangChainStreamEvent("step", name, "running", f"正在{name}...")
        steps.append(AgentStep(name, "completed", summary))
        yield LangChainStreamEvent("step", name, "completed", summary)

    def _messages(self, system: str, human: str) -> list[Any]:
        return [SystemMessage(content=system), HumanMessage(content=human)]

    def _llm(self, temperature: float = 0.1, streaming: bool = False) -> Any:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            streaming=streaming,
        )

    def _invoke_text(self, messages: list[Any], temperature: float = 0.1) -> str:
        response = self._llm(temperature=temperature).invoke(messages)
        return message_content_to_text(response.content)

    def _stream_text(self, messages: list[Any], temperature: float = 0.3) -> Iterator[str]:
        try:
            for chunk in self._llm(temperature=temperature, streaming=True).stream(messages):
                text = message_content_to_text(chunk.content)
                if text:
                    yield text
        except Exception:
            text = self._invoke_text(messages, temperature=temperature)
            for token in text:
                yield token

    def _parse_chart_config(self, raw: str, result: pd.DataFrame) -> dict[str, Any]:
        text = raw.strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"chart_type": "table", "x": "", "y": "", "size": "", "color": "", "reason": raw}
        if not isinstance(parsed, dict):
            return {"chart_type": "table", "x": "", "y": "", "size": "", "color": "", "reason": "模型图表建议格式无效，回退表格。"}

        valid_columns = {str(column) for column in result.columns}
        for key in ["x", "y", "size", "color"]:
            value = str(parsed.get(key, "") or "")
            parsed[key] = value if value in valid_columns else ""
        parsed["chart_type"] = str(parsed.get("chart_type", "table")).lower()
        parsed["reason"] = str(parsed.get("reason", "LangChain Agent 推荐图表。"))
        return parsed


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def format_history(history: list[ConversationTurn]) -> str:
    if not history:
        return "无"
    lines: list[str] = []
    for index, turn in enumerate(history[-6:], start=1):
        lines.append(f"{index}. 用户问题：{turn.question}")
        if turn.sql:
            lines.append(f"   已执行 SQL：{turn.sql}")
        if turn.analysis:
            lines.append(f"   结论摘要：{turn.analysis[:300]}")
    return "\n".join(lines)
