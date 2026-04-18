from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from openai import OpenAI

from .schema import SchemaProfile


FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum)\b",
    re.IGNORECASE,
)


@dataclass
class RepairStep:
    attempt: int
    sql: str
    error: str


@dataclass
class AgentStep:
    name: str
    status: str
    summary: str
    sql: str = ""
    error: str = ""


@dataclass
class AgentRun:
    question: str
    final_sql: str
    result: pd.DataFrame
    analysis: str
    chart_instruction: str
    repair_steps: list[RepairStep] = field(default_factory=list)
    steps: list[AgentStep] = field(default_factory=list)
    chart_config: dict[str, Any] | None = None


class SQLAgent:
    def __init__(self, max_rows: int = 500):
        self.base_url = os.getenv("LLM_BASE_URL") or None
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.max_rows = max_rows

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def run(self, question: str, schema: SchemaProfile, connection: sqlite3.Connection) -> AgentRun:
        if not self.is_configured:
            raise RuntimeError("未配置大模型 API。请设置 LLM_API_KEY、LLM_MODEL 和可选的 LLM_BASE_URL。")

        repair_steps: list[RepairStep] = []
        sql = self.generate_sql(question, schema)

        for attempt in range(3):
            try:
                result = self.execute_sql(connection, sql)
                analysis, chart_instruction = self.explain_result(question, sql, result)
                return AgentRun(
                    question=question,
                    final_sql=sql,
                    result=result,
                    analysis=analysis,
                    chart_instruction=chart_instruction,
                    repair_steps=repair_steps,
                )
            except Exception as exc:
                error = str(exc)
                repair_steps.append(RepairStep(attempt=attempt + 1, sql=sql, error=error))
                if attempt >= 2:
                    raise
                sql = self.repair_sql(question, schema, sql, error)

        raise RuntimeError("SQL Agent 未能生成可执行查询。")

    def execute_sql(self, connection: sqlite3.Connection, sql: str) -> pd.DataFrame:
        clean_sql = normalize_sql(sql)
        validate_read_only_sql(clean_sql)
        limited_sql = add_limit(clean_sql, self.max_rows)
        return pd.read_sql_query(limited_sql, connection)

    def generate_sql(self, question: str, schema: SchemaProfile) -> str:
        unavailable_sql = unavailable_concept_sql(question, schema)
        if unavailable_sql:
            return unavailable_sql
        messages = [
            {"role": "system", "content": sql_system_prompt()},
            {
                "role": "user",
                "content": (
                    "请基于下面的数据库 schema 生成 SQLite 查询。\n\n"
                    f"{schema.to_llm_context()}\n\n"
                    f"用户问题：{question}\n\n"
                    "只输出 SQL，不要解释，不要 Markdown。"
                ),
            },
        ]
        return self.chat(messages)

    def repair_sql(self, question: str, schema: SchemaProfile, sql: str, error: str) -> str:
        messages = [
            {"role": "system", "content": sql_system_prompt()},
            {
                "role": "user",
                "content": (
                    "下面的 SQL 在 SQLite 执行失败，请在保持用户意图的前提下修复。\n\n"
                    f"Schema:\n{schema.to_llm_context()}\n\n"
                    f"用户问题：{question}\n\n"
                    f"失败 SQL：\n{sql}\n\n"
                    f"错误信息：{error}\n\n"
                    "只输出修复后的 SQL，不要解释，不要 Markdown。"
                ),
            },
        ]
        return self.chat(messages)

    def explain_result(self, question: str, sql: str, result: pd.DataFrame) -> tuple[str, str]:
        preview = result.head(30).to_csv(index=False)
        columns = ", ".join(map(str, result.columns))
        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深数据分析 Agent。请用中文给出简洁但有业务价值的结论，"
                    "包括关键发现、可能原因、下一步分析建议。"
                    "只能基于 SQL、结果字段和结果预览解释；"
                    "不要补充结果中没有的指标、维度或业务事实。"
                    "如果结果提示某个字段/主题在 Schema 中不存在，必须明确说明无法分析，不能编造替代数据。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n\n"
                    f"SQL：\n{sql}\n\n"
                    f"结果字段：{columns}\n\n"
                    f"查询结果预览：\n{preview}\n\n"
                    "请输出两段：\n"
                    "1. 深度分析：3-5 条要点。\n"
                    "2. 图表建议：一句话说明适合什么图。"
                ),
            },
        ]
        content = self.chat(messages, temperature=0.3)
        marker = "图表建议"
        if marker in content:
            analysis, chart = content.split(marker, 1)
            return analysis.strip(), chart.replace("：", "", 1).strip()
        return content.strip(), "根据结果字段自动选择图表。"

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""


def sql_system_prompt() -> str:
    return (
        "你是一个只生成 SQLite 兼容 SELECT 查询的数据分析 Agent。"
        "必须遵守：只能输出一条只读 SQL；只能使用 SELECT 或 WITH；"
        "不要使用 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE、PRAGMA；"
        "字段或表名如包含特殊字符必须用双引号包裹；"
        "只能使用 schema 中真实存在的表和字段；"
        "多表分析时应优先使用同名标识字段关联，例如 customer_id、product_id、order_id；"
        "如需要销售额等衍生指标，可以用数量*价格等字段组合，但不要臆造不存在字段；"
        "如果用户询问的指标或维度在 schema 中不存在，不能用相似字段强行替代，"
        "应返回一条 SELECT 常量说明，例如 SELECT '当前 Schema 没有退款字段，无法分析退款率' AS schema_notice。"
        "特别注意：city_tier 只代表城市层级，不代表用户所在具体城市；"
        "没有 refund/return 字段时不能分析退款、退货、退款率。"
    )


def unavailable_concept_sql(question: str, schema: SchemaProfile) -> str:
    notice = unavailable_concept_notice(question, schema)
    if not notice:
        return ""
    escaped = notice.replace("'", "''")
    return f"SELECT '{escaped}' AS schema_notice"


def unavailable_concept_notice(question: str, schema: SchemaProfile) -> str:
    lowered_question = question.lower()
    available_columns = {column.name.lower() for table in schema.tables for column in table.columns}

    if any(token in lowered_question for token in ["退款", "退货", "refund", "return"]):
        has_refund = any("refund" in column or "return" in column or "退" in column for column in available_columns)
        if not has_refund:
            return "当前 Schema 没有退款或退货相关字段/表，无法分析退款金额、退货或退款率。可以先分析订单数、销售额、客单价、曝光、点击和购买转化。"

    asks_exact_city = any(
        token in lowered_question
        for token in ["所在城市", "具体城市", "城市分布", "各城市", "哪个城市", "city name", "user city", "customer city"]
    )
    if asks_exact_city:
        exact_city_columns = {"city", "city_name", "user_city", "customer_city", "region", "region_name", "province"}
        has_exact_city = bool(available_columns & exact_city_columns)
        has_city_tier = "city_tier" in available_columns
        if not has_exact_city and has_city_tier:
            return "当前 Schema 没有用户所在具体城市字段，只有 city_tier 城市层级字段；无法分析具体城市，只能按城市层级分组。"
        if not has_exact_city:
            return "当前 Schema 没有用户所在城市、区域或省份字段，无法按具体城市分析。"

    return ""


def normalize_sql(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    sql = sql.rstrip(";").strip()
    return sql


def validate_read_only_sql(sql: str) -> None:
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise ValueError("只允许执行 SELECT 或 WITH 开头的只读 SQL。")
    if FORBIDDEN_SQL.search(sql):
        raise ValueError("检测到写入或管理类 SQL 关键字，已阻止执行。")
    if ";" in sql:
        raise ValueError("只允许执行单条 SQL，不允许包含分号。")


def add_limit(sql: str, max_rows: int) -> str:
    if re.search(r"\blimit\s+\d+\b", sql, re.IGNORECASE):
        return sql
    return f"{sql}\nLIMIT {int(max_rows)}"


def summarize_dataframe(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": len(frame),
        "columns": list(frame.columns),
        "numeric_columns": frame.select_dtypes(include=["number"]).columns.tolist(),
    }
