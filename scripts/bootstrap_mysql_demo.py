from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Boolean, Date, Float, Integer, String, create_engine, text


DEFAULT_URL = "mysql+pymysql://agent:agent_demo_123@127.0.0.1:3307/data_agent_demo"
DEFAULT_CSV = Path(__file__).resolve().parents[1] / "淘宝用户行为.csv"
RANDOM_SEED = 42

CHANNELS = ["Search", "Recommendation", "Promotion", "Live", "Category Page"]
DEVICES = ["iOS", "Android", "Desktop", "Mini Program"]
BRANDS = [
    "Northline",
    "Mellow",
    "UrbanNest",
    "Nova",
    "Luma",
    "Horizon",
    "PureDay",
    "Kite",
    "Muse",
    "Atlas",
]
PRICE_BINS = [0, 80, 300, 800, 2000, np.inf]
PRICE_LABELS = ["低价", "平价", "中价", "高价", "奢华"]


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    raw_orders = load_orders(args.csv)
    customers = build_customers(raw_orders, rng)
    products = build_products(raw_orders, args.products, rng)
    orders = build_orders(raw_orders, products, rng)
    exposures = build_exposures(orders, customers, products, args.background_exposures, rng)
    clicks = build_clicks(exposures, rng)

    tables = {
        "dim_customers": customers,
        "dim_products": products,
        "fact_orders": orders,
        "fact_product_exposures": exposures,
        "fact_product_clicks": clicks,
    }

    print_summary(tables)
    validate_tables(tables)

    if args.dry_run:
        print("Dry run complete. No database writes were performed.")
        return

    engine = create_engine(args.url)
    write_tables(engine, tables, replace=args.replace)
    print(f"MySQL demo database is ready: {args.url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a 5-table MySQL demo dataset for the data analysis Agent.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to the source order CSV.")
    parser.add_argument("--url", default=DEFAULT_URL, help="SQLAlchemy MySQL URL.")
    parser.add_argument("--products", type=int, default=10_000, help="Number of synthetic products to generate.")
    parser.add_argument("--background-exposures", type=int, default=120_000, help="Extra non-purchase-path exposures.")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed for reproducible data generation.")
    parser.add_argument("--replace", action="store_true", help="Drop and recreate the demo tables.")
    parser.add_argument("--dry-run", action="store_true", help="Generate and validate tables without writing to MySQL.")
    return parser.parse_args()


def load_orders(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    df = pd.read_csv(path)
    df = df.drop(columns=[column for column in df.columns if str(column).startswith("Unnamed:")])
    required = ["invoice_no", "customer_id", "gender", "age", "category", "quantity", "price", "payment_method", "invoice_date"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    df = df[required].copy()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce").dt.date
    if df["invoice_date"].isna().any():
        raise ValueError("invoice_date contains invalid date values.")
    return df


def build_customers(orders: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    customers = orders[["customer_id", "gender", "age"]].drop_duplicates("customer_id").copy()
    customers["age_group"] = pd.cut(
        customers["age"],
        bins=[17, 24, 34, 44, 54, 64, 120],
        labels=["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
        right=True,
    ).astype(str)
    customers["city_tier"] = rng.choice(["一线", "新一线", "二线", "三线及以下"], size=len(customers), p=[0.18, 0.28, 0.32, 0.22])
    customers["member_level"] = rng.choice(["普通", "银卡", "金卡", "黑金"], size=len(customers), p=[0.56, 0.25, 0.15, 0.04])
    return customers.sort_values("customer_id").reset_index(drop=True)


def build_products(orders: pd.DataFrame, product_count: int, rng: np.random.Generator) -> pd.DataFrame:
    category_counts = allocate_counts(orders["category"].value_counts(normalize=True).sort_index(), product_count)
    rows: list[dict[str, object]] = []
    product_number = 1

    for category, count in category_counts.items():
        prices = orders.loc[orders["category"] == category, "price"].astype(float)
        mean = float(prices.mean())
        std = max(float(prices.std()), mean * 0.18, 10.0)
        generated_prices = np.clip(rng.normal(mean, std, count), 5.0, max(mean + 3 * std, 20.0))
        hotness = np.clip(rng.normal(1.0, 0.32, count), 0.12, None)

        for index in range(count):
            product_id = f"P{product_number:05d}"
            list_price = round(float(generated_prices[index]), 2)
            rows.append(
                {
                    "product_id": product_id,
                    "category": category,
                    "product_name": f"{category} 商品 {index + 1:04d}",
                    "brand": rng.choice(BRANDS),
                    "list_price": list_price,
                    "price_band": price_band(list_price),
                    "product_hotness": round(float(hotness[index]), 4),
                }
            )
            product_number += 1

    return pd.DataFrame(rows)


def allocate_counts(shares: pd.Series, total: int) -> dict[str, int]:
    raw = shares * total
    counts = raw.astype(int)
    counts[counts < 1] = 1
    remainder = total - int(counts.sum())
    fractions = (raw - np.floor(raw)).sort_values(ascending=False)
    if remainder > 0:
        for category in fractions.index[:remainder]:
            counts.loc[category] += 1
    elif remainder < 0:
        for category in fractions.sort_values().index[: abs(remainder)]:
            if counts.loc[category] > 1:
                counts.loc[category] -= 1
    return counts.astype(int).to_dict()


def price_band(price: float) -> str:
    return str(pd.cut(pd.Series([price]), PRICE_BINS, labels=PRICE_LABELS, right=False).iloc[0])


def build_orders(orders: pd.DataFrame, products: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    product_groups = {
        category: group[["product_id", "product_hotness"]].reset_index(drop=True)
        for category, group in products.groupby("category")
    }
    assigned_products: list[str] = []
    for category in orders["category"]:
        candidates = product_groups[category]
        weights = candidates["product_hotness"].to_numpy(dtype=float)
        weights = weights / weights.sum()
        assigned_products.append(str(rng.choice(candidates["product_id"].to_numpy(), p=weights)))

    result = orders.copy()
    result.insert(2, "product_id", assigned_products)
    result = result.rename(columns={"invoice_no": "order_id", "price": "unit_price", "invoice_date": "order_date"})
    result["order_amount"] = (result["quantity"].astype(float) * result["unit_price"].astype(float)).round(2)
    return result[
        ["order_id", "customer_id", "product_id", "category", "quantity", "unit_price", "order_amount", "payment_method", "order_date"]
    ]


def build_exposures(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    background_count: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    path_counts = np.clip(rng.poisson(1.35, len(orders)) + 1, 1, 5)
    repeated_orders = orders.loc[orders.index.repeat(path_counts)].reset_index(drop=True)
    purchase_offsets = rng.integers(0, 15, size=len(repeated_orders))
    purchase_dates = pd.to_datetime(repeated_orders["order_date"]) - pd.to_timedelta(purchase_offsets, unit="D")

    path_exposures = pd.DataFrame(
        {
            "customer_id": repeated_orders["customer_id"].to_numpy(),
            "product_id": repeated_orders["product_id"].to_numpy(),
            "category": repeated_orders["category"].to_numpy(),
            "exposure_date": purchase_dates.dt.date,
            "channel": rng.choice(CHANNELS, size=len(repeated_orders), p=[0.25, 0.34, 0.18, 0.08, 0.15]),
            "device_type": rng.choice(DEVICES, size=len(repeated_orders), p=[0.36, 0.42, 0.12, 0.10]),
            "is_purchase_path": True,
        }
    )

    product_weights = products["product_hotness"].to_numpy(dtype=float)
    product_weights = product_weights / product_weights.sum()
    background_products = products.iloc[rng.choice(products.index.to_numpy(), size=background_count, p=product_weights)]
    customer_ids = customers["customer_id"].to_numpy()
    min_date = pd.to_datetime(orders["order_date"]).min()
    max_date = pd.to_datetime(orders["order_date"]).max()
    date_offsets = rng.integers(0, int((max_date - min_date).days) + 1, size=background_count)

    background_exposures = pd.DataFrame(
        {
            "customer_id": rng.choice(customer_ids, size=background_count),
            "product_id": background_products["product_id"].to_numpy(),
            "category": background_products["category"].to_numpy(),
            "exposure_date": (min_date + pd.to_timedelta(date_offsets, unit="D")).date,
            "channel": rng.choice(CHANNELS, size=background_count, p=[0.27, 0.30, 0.20, 0.08, 0.15]),
            "device_type": rng.choice(DEVICES, size=background_count, p=[0.34, 0.44, 0.12, 0.10]),
            "is_purchase_path": False,
        }
    )

    exposures = pd.concat([path_exposures, background_exposures], ignore_index=True)
    exposures.insert(0, "exposure_id", [f"E{index:07d}" for index in range(1, len(exposures) + 1)])
    return exposures


def build_clicks(exposures: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    channel_bonus = exposures["channel"].map(
        {"Search": 0.03, "Recommendation": 0.04, "Promotion": 0.02, "Live": 0.05, "Category Page": 0.0}
    ).fillna(0.0)
    base_rate = np.where(exposures["is_purchase_path"].to_numpy(dtype=bool), 0.32, 0.16)
    click_probability = np.clip(base_rate + channel_bonus.to_numpy(), 0.02, 0.62)
    clicked = rng.random(len(exposures)) < click_probability
    clicks = exposures.loc[clicked, ["exposure_id", "customer_id", "product_id", "category", "exposure_date", "channel", "device_type"]].copy()
    click_offsets = rng.integers(0, 2, size=len(clicks))
    clicks["click_date"] = (pd.to_datetime(clicks["exposure_date"]) + pd.to_timedelta(click_offsets, unit="D")).dt.date
    clicks = clicks.drop(columns=["exposure_date"])
    clicks.insert(0, "click_id", [f"K{index:07d}" for index in range(1, len(clicks) + 1)])
    return clicks[["click_id", "exposure_id", "customer_id", "product_id", "category", "click_date", "channel", "device_type"]]


def print_summary(tables: dict[str, pd.DataFrame]) -> None:
    for name, frame in tables.items():
        print(f"{name}: {len(frame):,} rows x {len(frame.columns)} columns")


def validate_tables(tables: dict[str, pd.DataFrame]) -> None:
    orders = tables["fact_orders"]
    products = tables["dim_products"]
    customers = tables["dim_customers"]
    exposures = tables["fact_product_exposures"]
    clicks = tables["fact_product_clicks"]

    product_ids = set(products["product_id"])
    customer_ids = set(customers["customer_id"])
    exposure_ids = set(exposures["exposure_id"])

    assert len(products) >= 9_500, "Product table should contain about 10,000 rows."
    assert orders["product_id"].isin(product_ids).all(), "All orders must map to products."
    assert orders["customer_id"].isin(customer_ids).all(), "All orders must map to customers."
    assert exposures["product_id"].isin(product_ids).all(), "All exposures must map to products."
    assert exposures["customer_id"].isin(customer_ids).all(), "All exposures must map to customers."
    assert clicks["product_id"].isin(product_ids).all(), "All clicks must map to products."
    assert clicks["customer_id"].isin(customer_ids).all(), "All clicks must map to customers."
    assert clicks["exposure_id"].isin(exposure_ids).all(), "All clicks must map to exposures."
    assert set(products["category"]) == set(orders["category"]), "All order categories should be present in products."


def write_tables(engine, tables: dict[str, pd.DataFrame], replace: bool) -> None:
    table_order = ["dim_customers", "dim_products", "fact_orders", "fact_product_exposures", "fact_product_clicks"]
    dtype_map = table_dtypes()
    with engine.begin() as connection:
        if replace:
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table_name in reversed(table_order):
                connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        for table_name in table_order:
            if_exists = "replace" if replace else "fail"
            tables[table_name].to_sql(
                table_name,
                connection,
                if_exists=if_exists,
                index=False,
                chunksize=5_000,
                dtype=dtype_map[table_name],
            )

        add_mysql_constraints(connection)


def table_dtypes() -> dict[str, dict[str, object]]:
    return {
        "dim_customers": {
            "customer_id": String(32),
            "gender": String(16),
            "age": Integer(),
            "age_group": String(16),
            "city_tier": String(16),
            "member_level": String(16),
        },
        "dim_products": {
            "product_id": String(32),
            "category": String(64),
            "product_name": String(128),
            "brand": String(64),
            "list_price": Float(),
            "price_band": String(16),
            "product_hotness": Float(),
        },
        "fact_orders": {
            "order_id": String(32),
            "customer_id": String(32),
            "product_id": String(32),
            "category": String(64),
            "quantity": Integer(),
            "unit_price": Float(),
            "order_amount": Float(),
            "payment_method": String(32),
            "order_date": Date(),
        },
        "fact_product_exposures": {
            "exposure_id": String(32),
            "customer_id": String(32),
            "product_id": String(32),
            "category": String(64),
            "exposure_date": Date(),
            "channel": String(32),
            "device_type": String(32),
            "is_purchase_path": Boolean(),
        },
        "fact_product_clicks": {
            "click_id": String(32),
            "exposure_id": String(32),
            "customer_id": String(32),
            "product_id": String(32),
            "category": String(64),
            "click_date": Date(),
            "channel": String(32),
            "device_type": String(32),
        },
    }


def add_mysql_constraints(connection) -> None:
    statements = [
        "ALTER TABLE dim_customers ADD PRIMARY KEY (customer_id)",
        "ALTER TABLE dim_products ADD PRIMARY KEY (product_id)",
        "ALTER TABLE fact_orders ADD PRIMARY KEY (order_id)",
        "ALTER TABLE fact_product_exposures ADD PRIMARY KEY (exposure_id)",
        "ALTER TABLE fact_product_clicks ADD PRIMARY KEY (click_id)",
        "CREATE INDEX idx_orders_customer ON fact_orders (customer_id)",
        "CREATE INDEX idx_orders_product ON fact_orders (product_id)",
        "CREATE INDEX idx_orders_segment ON fact_orders (category, order_date)",
        "CREATE INDEX idx_exposures_customer_product ON fact_product_exposures (customer_id, product_id)",
        "CREATE INDEX idx_exposures_product_date ON fact_product_exposures (product_id, exposure_date)",
        "CREATE INDEX idx_clicks_customer_product ON fact_product_clicks (customer_id, product_id)",
        "CREATE INDEX idx_clicks_exposure ON fact_product_clicks (exposure_id)",
        "ALTER TABLE fact_orders ADD CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id)",
        "ALTER TABLE fact_orders ADD CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES dim_products(product_id)",
        "ALTER TABLE fact_product_exposures ADD CONSTRAINT fk_exposures_customer FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id)",
        "ALTER TABLE fact_product_exposures ADD CONSTRAINT fk_exposures_product FOREIGN KEY (product_id) REFERENCES dim_products(product_id)",
        "ALTER TABLE fact_product_clicks ADD CONSTRAINT fk_clicks_exposure FOREIGN KEY (exposure_id) REFERENCES fact_product_exposures(exposure_id)",
        "ALTER TABLE fact_product_clicks ADD CONSTRAINT fk_clicks_customer FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id)",
        "ALTER TABLE fact_product_clicks ADD CONSTRAINT fk_clicks_product FOREIGN KEY (product_id) REFERENCES dim_products(product_id)",
    ]
    for statement in statements:
        connection.execute(text(statement))


if __name__ == "__main__":
    main()
