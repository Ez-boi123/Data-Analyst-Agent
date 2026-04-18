from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure


@dataclass
class ChartSpec:
    chart_type: str
    title: str
    figure: Figure | None
    reason: str


def build_chart(frame: pd.DataFrame, instruction: str | dict[str, Any] = "") -> ChartSpec:
    if frame.empty:
        return ChartSpec("table", "查询结果", None, "结果为空，展示表格更清晰")

    df = frame.copy()
    date_columns = detect_date_columns(df)
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_columns = [
        column
        for column in df.columns
        if column not in numeric_columns and column not in date_columns and df[column].nunique(dropna=True) <= 30
    ]
    structured_instruction, text_instruction = normalize_instruction(instruction)
    instructed = build_structured_chart(df, structured_instruction)
    if instructed:
        return instructed
    instructed = build_instructed_chart(df, text_instruction, numeric_columns, categorical_columns, date_columns)
    if instructed:
        return instructed

    if date_columns and numeric_columns:
        x_axis = date_columns[0]
        y_axis = numeric_columns[0]
        df[x_axis] = pd.to_datetime(df[x_axis], errors="coerce")
        df = df.dropna(subset=[x_axis]).sort_values(x_axis)
        figure = px.line(df, x=x_axis, y=y_axis, markers=True, title=f"{y_axis} 趋势")
        return ChartSpec("line", f"{y_axis} 趋势", figure, "识别到时间字段和数值指标")

    if categorical_columns and numeric_columns:
        x_axis = categorical_columns[0]
        y_axis = numeric_columns[0]
        if len(df) <= 12 and df[y_axis].ge(0).all():
            figure = px.pie(df, names=x_axis, values=y_axis, title=f"{x_axis} 占比")
            return ChartSpec("pie", f"{x_axis} 占比", figure, "分类数量较少，适合占比图")
        figure = px.bar(df, x=x_axis, y=y_axis, title=f"{x_axis} 对比 {y_axis}")
        figure.update_layout(xaxis_tickangle=-30)
        return ChartSpec("bar", f"{x_axis} 对比 {y_axis}", figure, "识别到分类维度和数值指标")

    if len(numeric_columns) >= 2:
        figure = px.scatter(df, x=numeric_columns[0], y=numeric_columns[1], title="数值关系散点图")
        return ChartSpec("scatter", "数值关系散点图", figure, "识别到多个数值字段")

    return ChartSpec("table", "查询结果", None, "结果结构更适合表格阅读")


def normalize_instruction(instruction: str | dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if isinstance(instruction, dict):
        return instruction, str(instruction.get("reason", ""))
    if not instruction:
        return None, ""
    text = str(instruction).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed, str(parsed.get("reason", text))
        except json.JSONDecodeError:
            pass
    return None, text


def build_structured_chart(frame: pd.DataFrame, config: dict[str, Any] | None) -> ChartSpec | None:
    if not config:
        return None

    chart_type = str(config.get("chart_type", "")).lower()
    reason = str(config.get("reason", "按 LangChain Agent 结构化图表建议生成"))
    x_axis = resolve_column(frame, config.get("x"))
    y_axis = resolve_column(frame, config.get("y"))
    size_axis = resolve_column(frame, config.get("size"))
    color_axis = resolve_column(frame, config.get("color"))

    if chart_type == "table":
        return ChartSpec("table", "查询结果", None, reason or "模型建议使用表格展示")
    if not chart_type:
        return None
    if chart_type == "bubble" and x_axis and y_axis:
        figure = px.scatter(
            frame,
            x=x_axis,
            y=y_axis,
            size=size_axis,
            color=color_axis,
            hover_data=[column for column in frame.columns if column not in {x_axis, y_axis, size_axis, color_axis}][:8],
            title=f"{x_axis} vs {y_axis} 气泡图",
        )
        return ChartSpec("bubble", f"{x_axis} vs {y_axis} 气泡图", figure, reason)
    if chart_type == "scatter" and x_axis and y_axis:
        figure = px.scatter(frame, x=x_axis, y=y_axis, color=color_axis, title=f"{x_axis} vs {y_axis} 散点图")
        return ChartSpec("scatter", f"{x_axis} vs {y_axis} 散点图", figure, reason)
    if chart_type == "line" and x_axis and y_axis:
        chart_frame = frame.copy()
        chart_frame[x_axis] = pd.to_datetime(chart_frame[x_axis], errors="coerce")
        if chart_frame[x_axis].notna().any():
            chart_frame = chart_frame.dropna(subset=[x_axis]).sort_values(x_axis)
        figure = px.line(chart_frame, x=x_axis, y=y_axis, color=color_axis, markers=True, title=f"{y_axis} 趋势")
        return ChartSpec("line", f"{y_axis} 趋势", figure, reason)
    if chart_type == "bar" and x_axis and y_axis:
        figure = px.bar(frame, x=x_axis, y=y_axis, color=color_axis, title=f"{x_axis} 对比 {y_axis}")
        figure.update_layout(xaxis_tickangle=-30)
        return ChartSpec("bar", f"{x_axis} 对比 {y_axis}", figure, reason)
    if chart_type == "pie" and x_axis and y_axis:
        figure = px.pie(frame, names=x_axis, values=y_axis, title=f"{x_axis} 占比")
        return ChartSpec("pie", f"{x_axis} 占比", figure, reason)
    return None


def resolve_column(frame: pd.DataFrame, value: Any) -> str | None:
    if value is None:
        return None
    target = str(value).strip()
    if not target:
        return None
    for column in frame.columns:
        if str(column) == target:
            return column
    lowered = target.lower()
    for column in frame.columns:
        if str(column).lower() == lowered:
            return column
    return None


def build_instructed_chart(
    frame: pd.DataFrame,
    instruction: str,
    numeric_columns: list[str],
    categorical_columns: list[str],
    date_columns: list[str],
) -> ChartSpec | None:
    text = instruction.lower()
    if not text.strip():
        return None

    if any(keyword in text for keyword in ["气泡", "bubble"]) and len(numeric_columns) >= 2:
        x_axis = pick_column(numeric_columns, ["曝光", "exposure", "impression"]) or numeric_columns[0]
        y_axis = pick_column(numeric_columns, ["点击", "click"]) or numeric_columns[1]
        size_axis = (
            pick_column(numeric_columns, ["购买", "purchase", "buyer", "用户数", "人数"])
            or pick_column(numeric_columns, ["订单", "order"])
            or (numeric_columns[2] if len(numeric_columns) >= 3 else None)
        )
        color_axis = pick_column(categorical_columns, ["品类", "category"]) or (categorical_columns[0] if categorical_columns else None)
        hover_columns = [column for column in frame.columns if column not in {x_axis, y_axis, size_axis, color_axis}]
        figure = px.scatter(
            frame,
            x=x_axis,
            y=y_axis,
            size=size_axis,
            color=color_axis,
            hover_data=hover_columns[:8],
            title=f"{x_axis} vs {y_axis} 气泡图",
        )
        return ChartSpec("bubble", f"{x_axis} vs {y_axis} 气泡图", figure, "按模型建议生成气泡散点图")

    if any(keyword in text for keyword in ["散点", "scatter"]) and len(numeric_columns) >= 2:
        color_axis = categorical_columns[0] if categorical_columns else None
        figure = px.scatter(frame, x=numeric_columns[0], y=numeric_columns[1], color=color_axis, title="模型建议散点图")
        return ChartSpec("scatter", "模型建议散点图", figure, "按模型建议生成散点图")

    if any(keyword in text for keyword in ["折线", "趋势", "line"]) and date_columns and numeric_columns:
        x_axis = date_columns[0]
        y_axis = numeric_columns[0]
        chart_frame = frame.copy()
        chart_frame[x_axis] = pd.to_datetime(chart_frame[x_axis], errors="coerce")
        chart_frame = chart_frame.dropna(subset=[x_axis]).sort_values(x_axis)
        figure = px.line(chart_frame, x=x_axis, y=y_axis, markers=True, title=f"{y_axis} 趋势")
        return ChartSpec("line", f"{y_axis} 趋势", figure, "按模型建议生成趋势图")

    if any(keyword in text for keyword in ["柱状", "柱形", "bar"]) and categorical_columns and numeric_columns:
        figure = px.bar(frame, x=categorical_columns[0], y=numeric_columns[0], title=f"{categorical_columns[0]} 对比 {numeric_columns[0]}")
        figure.update_layout(xaxis_tickangle=-30)
        return ChartSpec("bar", f"{categorical_columns[0]} 对比 {numeric_columns[0]}", figure, "按模型建议生成柱状图")

    if any(keyword in text for keyword in ["饼", "占比", "pie"]) and categorical_columns and numeric_columns:
        figure = px.pie(frame, names=categorical_columns[0], values=numeric_columns[0], title=f"{categorical_columns[0]} 占比")
        return ChartSpec("pie", f"{categorical_columns[0]} 占比", figure, "按模型建议生成占比图")

    return None


def pick_column(columns: list[str], keywords: list[str]) -> str | None:
    for keyword in keywords:
        for column in columns:
            if keyword in str(column).lower():
                return column
    return None


def detect_date_columns(frame: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for column in frame.columns:
        lowered = str(column).lower()
        if any(token in lowered for token in ["date", "time", "day", "month", "日期", "时间"]):
            parsed = pd.to_datetime(frame[column], errors="coerce")
            if parsed.notna().mean() >= 0.6:
                candidates.append(column)
    return candidates
