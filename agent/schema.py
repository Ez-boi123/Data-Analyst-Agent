from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ColumnProfile:
    name: str
    pandas_type: str
    sqlite_type: str
    semantic_hint: str
    null_rate: float
    distinct_count: int
    sample_values: list[str]


@dataclass
class TableProfile:
    name: str
    row_count: int
    columns: list[ColumnProfile]


@dataclass
class RelationCandidate:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str


@dataclass
class SchemaProfile:
    tables: list[TableProfile]
    relations: list[RelationCandidate]

    def to_llm_context(self) -> str:
        lines: list[str] = []
        for table in self.tables:
            lines.append(f"Table `{table.name}`: {table.row_count} rows")
            for column in table.columns:
                samples = ", ".join(column.sample_values[:4])
                lines.append(
                    "- "
                    f"{column.name} ({column.sqlite_type}, pandas={column.pandas_type}, "
                    f"null_rate={column.null_rate:.1%}, distinct={column.distinct_count}, "
                    f"hint={column.semantic_hint}, samples=[{samples}])"
                )
        if self.relations:
            lines.append("Relation candidates:")
            for relation in self.relations:
                lines.append(
                    "- "
                    f"{relation.left_table}.{relation.left_column} -> "
                    f"{relation.right_table}.{relation.right_column}: {relation.reason}"
                )
        return "\n".join(lines)

    def as_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for table in self.tables:
            for column in table.columns:
                rows.append(
                    {
                        "表名": table.name,
                        "字段": column.name,
                        "类型": column.sqlite_type,
                        "业务含义猜测": column.semantic_hint,
                        "缺失率": f"{column.null_rate:.1%}",
                        "唯一值数": column.distinct_count,
                        "样例值": ", ".join(column.sample_values[:5]),
                    }
                )
        return rows


def profile_tables(tables: dict[str, pd.DataFrame]) -> SchemaProfile:
    table_profiles = [profile_table(table_name, frame) for table_name, frame in tables.items()]
    return SchemaProfile(tables=table_profiles, relations=infer_relations(tables))


def profile_table(table_name: str, frame: pd.DataFrame) -> TableProfile:
    columns = [profile_column(column, frame[column]) for column in frame.columns]
    return TableProfile(name=table_name, row_count=len(frame), columns=columns)


def profile_column(name: str, series: pd.Series) -> ColumnProfile:
    non_null = series.dropna()
    sample_values = [str(value) for value in non_null.astype(str).drop_duplicates().head(6).tolist()]
    return ColumnProfile(
        name=name,
        pandas_type=str(series.dtype),
        sqlite_type=to_sqlite_type(series),
        semantic_hint=guess_semantic_hint(name, series),
        null_rate=float(series.isna().mean()) if len(series) else 0.0,
        distinct_count=int(series.nunique(dropna=True)),
        sample_values=sample_values,
    )


def to_sqlite_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "INTEGER"
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TEXT"
    return "TEXT"


def guess_semantic_hint(name: str, series: pd.Series) -> str:
    lowered = name.lower()
    if lowered in {"id", "uid"} or lowered.endswith("_id") or "customer" in lowered:
        return "标识字段，可用于关联或去重"
    if any(token in lowered for token in ["date", "time", "day", "month"]):
        return "时间字段，适合趋势分析"
    if any(token in lowered for token in ["price", "amount", "revenue", "sales", "cost", "gmv"]):
        return "金额/数值指标，适合聚合分析"
    if any(token in lowered for token in ["qty", "quantity", "count", "num"]):
        return "数量指标，适合求和或均值"
    if pd.api.types.is_numeric_dtype(series):
        return "数值字段，适合统计分布或聚合"
    unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
    if unique_ratio < 0.2:
        return "分类维度，适合分组对比"
    return "文本字段，可能是明细或描述"


def infer_relations(tables: dict[str, pd.DataFrame]) -> list[RelationCandidate]:
    candidates: list[RelationCandidate] = []
    items = list(tables.items())
    for left_index, (left_table, left_frame) in enumerate(items):
        for right_table, right_frame in items[left_index + 1 :]:
            for left_column in left_frame.columns:
                for right_column in right_frame.columns:
                    reason = relation_reason(left_column, right_column, left_frame[left_column], right_frame[right_column])
                    if reason:
                        candidates.append(
                            RelationCandidate(
                                left_table=left_table,
                                left_column=left_column,
                                right_table=right_table,
                                right_column=right_column,
                                reason=reason,
                            )
                        )
    return candidates[:20]


def relation_reason(
    left_column: str,
    right_column: str,
    left_series: pd.Series,
    right_series: pd.Series,
) -> str | None:
    left_name = left_column.lower()
    right_name = right_column.lower()
    name_match = left_name == right_name and is_identifier_name(left_name)
    id_suffix_match = left_name.endswith("_id") and right_name.endswith("_id") and left_name == right_name
    if not (name_match or id_suffix_match):
        return None

    left_values = set(left_series.dropna().astype(str).drop_duplicates().head(50000))
    right_values = set(right_series.dropna().astype(str).drop_duplicates().head(50000))
    if not left_values or not right_values:
        return None
    overlap = len(left_values & right_values) / max(min(len(left_values), len(right_values)), 1)
    if overlap >= 0.05:
        return f"同名标识字段且样例值重合度约 {overlap:.0%}"
    return None


def is_identifier_name(name: str) -> bool:
    return name == "id" or name.endswith("_id") or name in {"customer", "product", "order", "user"}
