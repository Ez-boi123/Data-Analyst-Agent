from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.charts import build_chart
from agent.data_source import (
    DataCatalog,
    connection_from_catalog,
    load_default_sample,
    load_sqlalchemy_url,
    load_sqlite_file,
    load_sqlite_path,
    load_uploaded_files,
)
from agent.schema import SchemaProfile, profile_tables
from agent.langchain_agent import LangChainDataAgent, LangChainStreamEvent
from agent.sql_agent import SQLAgent


WORKDIR = Path(__file__).parent


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

st.set_page_config(
    page_title="通用数据分析 Agent Demo",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.4rem; max-width: 1280px; }
    h1, h2, h3 { letter-spacing: 0; }
    [data-testid="stMetricValue"] { font-size: 1.55rem; }
    .status-strip {
        border-left: 4px solid #1f77b4;
        background: #f6f9fc;
        padding: 0.75rem 1rem;
        margin: 0.25rem 0 1rem 0;
    }
    .repair-box {
        border: 1px solid #e6edf3;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.7rem;
        background: #fbfdff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def cached_default_catalog() -> DataCatalog:
    return load_default_sample(WORKDIR)


def build_catalog() -> DataCatalog:
    if st.session_state.source_mode == "上传 CSV / Excel":
        files = st.session_state.uploaded_files or []
        if files:
            return load_uploaded_files(files)
        return cached_default_catalog()

    if st.session_state.source_mode == "MySQL / SQLite / 数据库连接":
        sqlite_upload = st.session_state.sqlite_upload
        connection_text = (st.session_state.connection_text or "").strip()
        if sqlite_upload is not None:
            return load_sqlite_file(sqlite_upload)
        if connection_text:
            if "://" in connection_text:
                return load_sqlalchemy_url(connection_text)
            return load_sqlite_path(Path(connection_text).expanduser())
        return cached_default_catalog()

    return cached_default_catalog()


@st.cache_data(show_spinner=False)
def cached_profile(source_label: str, table_names: tuple[str, ...], row_count: int, tables: dict[str, pd.DataFrame]) -> SchemaProfile:
    return profile_tables(tables)


def show_schema(profile: SchemaProfile) -> None:
    schema_rows = profile.as_rows()
    st.dataframe(schema_rows, use_container_width=True, hide_index=True)
    if profile.relations:
        relation_rows = [
            {
                "左表": item.left_table,
                "左字段": item.left_column,
                "右表": item.right_table,
                "右字段": item.right_column,
                "依据": item.reason,
            }
            for item in profile.relations
        ]
        st.subheader("表关联候选")
        st.dataframe(relation_rows, use_container_width=True, hide_index=True)
    else:
        st.info("当前数据源暂未发现高置信度表关联候选。上传多表数据后，这里会展示可关联字段。")


def show_table_preview(catalog: DataCatalog) -> None:
    for table_name, frame in catalog.tables.items():
        with st.expander(f"{table_name} · {len(frame):,} 行 · {len(frame.columns)} 列", expanded=False):
            st.dataframe(frame.head(50), use_container_width=True)


def run_classic_agent(question: str, profile: SchemaProfile, connection: sqlite3.Connection) -> None:
    agent = SQLAgent(max_rows=st.session_state.max_rows)
    with st.spinner("Agent 正在理解问题、生成 SQL 并执行自修复..."):
        run = agent.run(question, profile, connection)
    st.session_state.last_run = run


def run_langchain_agent(question: str, profile: SchemaProfile, connection: sqlite3.Connection) -> None:
    agent = LangChainDataAgent(max_rows=st.session_state.max_rows)
    if not agent.is_configured:
        raise RuntimeError(agent.unavailable_reason)

    events: list[LangChainStreamEvent] = []
    analysis_text = ""

    st.subheader("LangChain Agent 流式执行")
    timeline_placeholder = st.empty()
    sql_placeholder = st.empty()
    analysis_placeholder = st.empty()

    for event in agent.stream(question, profile, connection):
        if event.event_type == "step":
            events.append(event)
            timeline_placeholder.markdown(format_stream_events(events))
            if event.sql:
                sql_placeholder.code(event.sql, language="sql")
            if event.error:
                sql_placeholder.error(event.error)
        elif event.event_type == "token":
            analysis_text += event.message
            analysis_placeholder.markdown(analysis_text)
        elif event.event_type == "final" and event.run is not None:
            st.session_state.last_run = event.run


def format_stream_events(events: list[LangChainStreamEvent]) -> str:
    status_map = {"running": "进行中", "completed": "完成", "failed": "失败"}
    lines = []
    for event in events:
        status = status_map.get(event.status, event.status)
        summary = event.message.replace("\n", " ")
        lines.append(f"- **{event.name}** · `{status}`：{summary}")
    return "\n".join(lines)


def render_last_run(section_key: str) -> None:
    run = st.session_state.get("last_run")
    if not run:
        st.info("先在“智能问数”中提交一个问题，这里会展示 SQL、图表和分析结论。")
        return

    left, right = st.columns([1.05, 1])
    with left:
        st.subheader("最终 SQL")
        st.code(run.final_sql, language="sql")
        st.subheader("查询结果")
        st.dataframe(run.result, use_container_width=True, hide_index=True, key=f"{section_key}_result_table")
    with right:
        chart = build_chart(run.result, run.chart_config or run.chart_instruction)
        st.subheader(chart.title)
        if chart.figure is None:
            st.caption(chart.reason)
        else:
            st.plotly_chart(chart.figure, use_container_width=True, key=f"{section_key}_result_chart")
            st.caption(f"自动图表选择：{chart.reason}")
        st.subheader("深度分析")
        st.markdown(run.analysis)
        if run.chart_instruction:
            st.caption(f"模型图表建议：{run.chart_instruction}")


def render_repair_steps() -> None:
    run = st.session_state.get("last_run")
    if not run:
        st.info("尚未执行问题。SQL 报错后，Agent 的修复轨迹会出现在这里。")
        return
    if not run.repair_steps:
        st.success("本次 SQL 首次执行成功，没有触发自修复。")
        st.code(run.final_sql, language="sql")
        return
    for step in run.repair_steps:
        st.markdown(
            f"""
            <div class="repair-box">
            <strong>第 {step.attempt} 次尝试失败</strong><br>
            错误信息：{step.error}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(step.sql, language="sql")
    st.subheader("修复后 SQL")
    st.code(run.final_sql, language="sql")


def model_status(agent: SQLAgent) -> None:
    if agent.is_configured:
        st.success(f"模型已配置：{agent.model}")
        if agent.base_url:
            st.caption(f"Base URL：{agent.base_url}")
    else:
        st.warning("未配置大模型 API。请复制 `.env.example` 为 `.env` 并填写 LLM_API_KEY / LLM_MODEL。")


def langchain_status(agent: LangChainDataAgent) -> None:
    if agent.is_configured:
        st.success(f"LangChain Agent 已就绪：{agent.model}")
    else:
        st.warning(agent.unavailable_reason or "LangChain Agent 未就绪。")


def main() -> None:
    st.title("通用数据分析 Agent Demo")
    st.markdown(
        '<div class="status-strip">面向任意业务表的智能分析工作台：自动理解 Schema、生成 SQL、执行自修复，并把查询结果转成图表和分析结论。</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("数据源")
        st.radio(
            "选择数据接入方式",
            ["内置样例", "上传 CSV / Excel", "MySQL / SQLite / 数据库连接"],
            key="source_mode",
        )
        st.file_uploader(
            "上传 CSV 或 Excel",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="uploaded_files",
            disabled=st.session_state.source_mode != "上传 CSV / Excel",
        )
        st.file_uploader(
            "上传 SQLite 文件",
            type=["sqlite", "sqlite3", "db"],
            key="sqlite_upload",
            disabled=st.session_state.source_mode != "MySQL / SQLite / 数据库连接",
        )
        st.text_input(
            "SQLite 路径或 SQLAlchemy URL",
            key="connection_text",
            placeholder="mysql+pymysql://agent:agent_demo_123@127.0.0.1:3307/data_agent_demo",
            disabled=st.session_state.source_mode != "MySQL / SQLite / 数据库连接",
        )

        st.divider()
        st.header("Agent 设置")
        st.radio(
            "Agent 模式",
            ["LangChain Agent", "经典 Agent"],
            key="agent_mode",
        )
        st.slider("最大返回行数", min_value=50, max_value=2000, value=500, step=50, key="max_rows")
        if st.session_state.agent_mode == "LangChain Agent":
            langchain_status(LangChainDataAgent(max_rows=st.session_state.max_rows))
        else:
            model_status(SQLAgent(max_rows=st.session_state.max_rows))

    try:
        catalog = build_catalog()
    except Exception as exc:
        st.error(f"数据源加载失败：{exc}")
        catalog = cached_default_catalog()

    if not catalog.tables:
        st.error("当前没有可用数据表。请上传 CSV、Excel 或 SQLite 数据库。")
        return

    profile = cached_profile(
        catalog.source_label,
        tuple(catalog.tables.keys()),
        catalog.row_count,
        catalog.tables,
    )
    connection = connection_from_catalog(catalog)

    metric_cols = st.columns(4)
    metric_cols[0].metric("数据源", catalog.source_label)
    metric_cols[1].metric("表数量", len(catalog.tables))
    metric_cols[2].metric("总行数", f"{catalog.row_count:,}")
    metric_cols[3].metric("字段数", sum(len(frame.columns) for frame in catalog.tables.values()))

    tabs = st.tabs(["数据源", "Schema 理解", "智能问数", "自修复过程", "深度分析"])

    with tabs[0]:
        st.subheader("数据表预览")
        show_table_preview(catalog)

    with tabs[1]:
        st.subheader("Schema Profile")
        show_schema(profile)
        with st.expander("提供给大模型的 Schema 上下文", expanded=False):
            st.code(profile.to_llm_context(), language="text")

    with tabs[2]:
        st.subheader("自然语言问数")
        examples = [
            "按年龄段和性别统计订单数、销售额、客单价。",
            "不同年龄和性别用户从曝光到点击再到购买的转化率是多少？",
            "年轻女性最偏好的商品品类是什么？和男性相比有什么差异？",
            "哪些品类高曝光高点击但购买转化低？",
            "按性别和年龄段分析支付方式偏好，并给出业务建议。",
        ]
        selected = st.selectbox("示例问题", [""] + examples)
        default_question = selected or "请找出这个数据集中最值得关注的业务变化，并给出 SQL。"
        question = st.text_area("输入你的分析问题", value=default_question, height=90)
        if st.button("运行 Agent", type="primary", use_container_width=True):
            try:
                if st.session_state.agent_mode == "LangChain Agent":
                    run_langchain_agent(question, profile, connection)
                else:
                    run_classic_agent(question, profile, connection)
                st.success("Agent 执行完成。")
            except Exception as exc:
                st.error(f"Agent 执行失败：{exc}")
        render_last_run("ask_tab")

    with tabs[3]:
        st.subheader("SQL 生成与自修复轨迹")
        render_repair_steps()

    with tabs[4]:
        st.subheader("分析结论与可视化")
        render_last_run("analysis_tab")


if __name__ == "__main__":
    main()
