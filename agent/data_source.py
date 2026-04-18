from __future__ import annotations

import io
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from sqlalchemy import create_engine, inspect, text


SUPPORTED_FILE_TYPES = ("csv", "xlsx", "xls")


@dataclass
class DataCatalog:
    """A normalized collection of tabular data ready to register in the demo engine."""

    source_label: str
    tables: dict[str, pd.DataFrame]

    @property
    def row_count(self) -> int:
        return sum(len(frame) for frame in self.tables.values())


def sanitize_identifier(value: str, fallback: str = "table") -> str:
    """Create a conservative SQL identifier from arbitrary file/sheet names."""

    value = Path(value).stem if value else fallback
    value = re.sub(r"\W+", "_", value, flags=re.UNICODE).strip("_")
    if not value:
        value = fallback
    if value[0].isdigit():
        value = f"{fallback}_{value}"
    return value[:48]


def normalize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Clean common spreadsheet artifacts without changing business semantics."""

    df = frame.copy()
    empty_unnamed = [
        col
        for col in df.columns
        if str(col).startswith("Unnamed:") and df[col].isna().mean() >= 0.98
    ]
    if empty_unnamed:
        df = df.drop(columns=empty_unnamed)

    seen: dict[str, int] = {}
    clean_columns: list[str] = []
    for index, column in enumerate(df.columns):
        name = str(column).strip() or f"column_{index + 1}"
        name = re.sub(r"\s+", "_", name)
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        clean_columns.append(name)
    df.columns = clean_columns
    return df


def load_default_sample(workdir: Path) -> DataCatalog:
    sample_path = workdir / "淘宝用户行为.csv"
    if not sample_path.exists():
        return DataCatalog("空白数据源", {})
    frame = pd.read_csv(sample_path)
    return DataCatalog("内置样例数据：淘宝用户行为.csv", {"sample_orders": normalize_dataframe(frame)})


def load_uploaded_files(files: list[BinaryIO]) -> DataCatalog:
    tables: dict[str, pd.DataFrame] = {}
    labels: list[str] = []

    for uploaded in files:
        name = getattr(uploaded, "name", "uploaded_file")
        labels.append(name)
        suffix = Path(name).suffix.lower()
        base_name = sanitize_identifier(name, "uploaded_table")

        if suffix == ".csv":
            content = uploaded.read()
            frame = pd.read_csv(io.BytesIO(content))
            tables[base_name] = normalize_dataframe(frame)
        elif suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(uploaded, sheet_name=None)
            for sheet_name, frame in sheets.items():
                table_name = sanitize_identifier(f"{base_name}_{sheet_name}", "sheet")
                tables[table_name] = normalize_dataframe(frame)
        else:
            raise ValueError(f"暂不支持文件类型：{suffix}")

    label = "上传文件：" + "、".join(labels)
    return DataCatalog(label, tables)


def load_sqlite_file(uploaded_file: BinaryIO) -> DataCatalog:
    """Read all user tables from an uploaded SQLite database into dataframes."""

    name = getattr(uploaded_file, "name", "uploaded.sqlite")
    content = uploaded_file.read()
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=True) as temp:
        temp.write(content)
        temp.flush()
        return load_sqlite_path(Path(temp.name), f"SQLite 文件：{name}")


def load_sqlite_path(path: Path, label: str | None = None) -> DataCatalog:
    if not path.exists():
        raise FileNotFoundError(f"SQLite 文件不存在：{path}")

    with sqlite3.connect(path) as connection:
        table_names = list_sqlite_tables(connection)
        tables = {
            table_name: normalize_dataframe(pd.read_sql_query(f'SELECT * FROM "{table_name}"', connection))
            for table_name in table_names
        }
    return DataCatalog(label or f"SQLite 文件：{path}", tables)


def load_sqlalchemy_url(url: str) -> DataCatalog:
    engine = create_engine(url)
    inspector = inspect(engine)
    table_names = sorted(set(inspector.get_table_names() + inspector.get_view_names()))
    tables: dict[str, pd.DataFrame] = {}
    with engine.connect() as connection:
        preparer = engine.dialect.identifier_preparer
        for table_name in table_names:
            quoted_table = preparer.quote(table_name)
            query = text(f"SELECT * FROM {quoted_table}")
            tables[table_name] = normalize_dataframe(pd.read_sql_query(query, connection))
    return DataCatalog(f"数据库连接：{safe_connection_label(url)}", tables)


def safe_connection_label(url: str) -> str:
    if "@" not in url:
        return url
    return url.split("@", 1)[1]


def list_sqlite_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row[0] for row in rows]


def register_tables(connection: sqlite3.Connection, tables: dict[str, pd.DataFrame]) -> None:
    for table_name, frame in tables.items():
        safe_name = sanitize_identifier(table_name)
        frame.to_sql(safe_name, connection, if_exists="replace", index=False)


def connection_from_catalog(catalog: DataCatalog) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    register_tables(connection, catalog.tables)
    return connection
