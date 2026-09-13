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
    assessment: dict[str, Any] | None = None


@dataclass
class RelationCandidate:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str
    assessment: dict[str, Any] | None = None


@dataclass
class SchemaProfile:
    tables: list[TableProfile]
    relations: list[RelationCandidate]
    assessment: dict[str, Any] | None = None

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
    schema = SchemaProfile(tables=table_profiles, relations=infer_relations(tables))
    evaluate_schema(schema, tables)
    return schema


def assessment(score: float | None, method: str, components: dict[str, float], warnings: list[str]) -> dict[str, Any]:
    return {
        "score": round(max(0.0, min(1.0, score)), 4) if score is not None else None,
        "method": method,
        "components": components,
        "warnings": warnings,
        "scope": "当前已加载数据的结构质量规则分；未验证问题匹配、业务语义或 SQL 正确性，不是正确概率。",
    }


def evaluate_schema(schema: SchemaProfile, tables: dict[str, pd.DataFrame]) -> None:
    warnings: list[str] = []
    for table in schema.tables:
        if not table.row_count or not table.columns:
            table.assessment = assessment(None, "无可评估的数据", {}, ["空表或无字段"])
            warnings.append(f"{table.name}：空表或无字段，总分按 0 计入")
            continue
        completeness = sum(1 - c.null_rate for c in table.columns) / len(table.columns)
        evidence = sum(bool(c.sample_values) for c in table.columns) / len(table.columns)
        table.assessment = assessment(
            0.8 * completeness + 0.2 * evidence,
            "80% 字段平均非空率 + 20% 有非空样例的字段占比",
            {"字段完整性": completeness, "样例证据覆盖": evidence},
            [f"{c.name}：缺失率 {c.null_rate:.1%}" for c in table.columns if c.null_rate > 0],
        )
        warnings.extend(f"{table.name}：{w}" for w in table.assessment["warnings"])

    for relation in schema.relations:
        left = tables[relation.left_table][relation.left_column]
        right = tables[relation.right_table][relation.right_column]
        left_values = relation_values(left)
        right_values = relation_values(right)
        # Higher-uniqueness side is only a candidate parent; this is not FK validation.
        left_unique = len(left_values) / max(int(left.notna().sum()), 1)
        right_unique = len(right_values) / max(int(right.notna().sum()), 1)
        child_values = left_values if right_unique >= left_unique else right_values
        coverage = len(left_values & right_values) / max(len(child_values), 1)
        uniqueness = max(left_unique, right_unique)
        completeness = min(float(left.notna().mean()), float(right.notna().mean()))
        compatible = to_sqlite_type(left) == to_sqlite_type(right) or {to_sqlite_type(left), to_sqlite_type(right)} <= {"INTEGER", "REAL"}
        issues = []
        if uniqueness < 1:
            issues.append("关联两侧均存在重复键，可能产生多对多计数膨胀")
        if coverage < 1:
            issues.append(f"候选子表关联键覆盖率 {coverage:.1%}，存在未匹配键")
        if completeness < 1:
            issues.append(f"关联键最低非空率 {completeness:.1%}")
        if not compatible:
            issues.append("关联键类型不兼容，关联评分为 0")
        relation.assessment = assessment(
            (0.5 * coverage + 0.3 * uniqueness + 0.2 * completeness) if compatible else 0,
            "类型兼容时：50% 候选子表键覆盖率 + 30% 较高侧唯一率 + 20% 较低侧非空率；唯一率较高侧视为候选父表",
            {"取值覆盖率": coverage, "候选父表唯一率": uniqueness, "关联键完整性": completeness, "类型兼容": float(compatible)},
            issues,
        )
        warnings.extend(f"{relation.left_table} ↔ {relation.right_table}：{w}" for w in issues)

    measured = [t.assessment["score"] for t in schema.tables if t.assessment["score"] is not None]
    if not measured:
        schema.assessment = assessment(None, "无可评估的数据", {}, warnings)
        return
    table_score = sum(measured) / len(schema.tables)
    components = {"表结构质量": table_score}
    score = table_score
    method = "单表：表结构质量；空表计 0"
    if len(schema.tables) > 1:
        # Penalize disconnected tables, not just the absence of all candidate edges.
        reachable_pairs = 0
        for table in schema.tables:
            reached = {table.name}
            while True:
                previous = len(reached)
                for relation in schema.relations:
                    if relation.left_table in reached or relation.right_table in reached:
                        reached.update([relation.left_table, relation.right_table])
                if len(reached) == previous:
                    break
            reachable_pairs += len(reached) - 1
        connectivity = reachable_pairs / (len(schema.tables) * (len(schema.tables) - 1))
        relation_score = sum(r.assessment["score"] for r in schema.relations) / max(len(schema.relations), 1)
        components.update({"关联质量": relation_score, "关联连通覆盖": connectivity})
        score = 0.6 * table_score + 0.4 * relation_score * connectivity
        method = "60% 表质量均值 + 40% 关联质量均值 × 可连通表对占比；空表计 0"
        if connectivity < 1:
            warnings.append("候选关联未连通所有表；当前候选发现仅支持同名标识字段，最多保留 20 条，不代表一定不可关联")
    schema.assessment = assessment(score, method, components, warnings)


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


def relation_values(series: pd.Series, limit: int | None = None) -> set:
    values = series.dropna().drop_duplicates()
    if limit is not None:
        values = values.head(limit)
    # Numeric equality treats 1 and 1.0 identically without rounding large integer IDs.
    return set(values.tolist()) if pd.api.types.is_numeric_dtype(series) else set(values.astype(str))


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

    left_values = relation_values(left_series, 50000)
    right_values = relation_values(right_series, 50000)
    if not left_values or not right_values:
        return None
    overlap = len(left_values & right_values) / max(min(len(left_values), len(right_values)), 1)
    if overlap >= 0.05:
        return f"同名标识字段且样例值重合度约 {overlap:.0%}"
    return None


def is_identifier_name(name: str) -> bool:
    return name == "id" or name.endswith("_id") or name in {"customer", "product", "order", "user"}
