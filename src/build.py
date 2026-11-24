"""Joins -> analytical tables (fact_order_items, fact_orders, dim_customers)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.clean import LOST_STATUSES
from src.labels import OTHER, category_label

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

INCOMPLETE_MONTH_THRESHOLD = 0.10  # a month with < 10% of the median monthly orders is partial
TOP_N_CATEGORIES = 20


def detect_complete_months(
    purchase_ts: pd.Series, threshold: float = INCOMPLETE_MONTH_THRESHOLD
) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame]:
    """Return (first, last) complete month and a table describing every month.

    A month is incomplete when it has fewer orders than `threshold` x the median
    monthly order count. The complete period is the span between the first and the
    last complete month.
    """
    months = purchase_ts.dt.to_period("M").dt.to_timestamp()
    counts = months.value_counts().sort_index()
    cutoff = threshold * counts.median()
    table = pd.DataFrame({"month": counts.index, "orders": counts.to_numpy()})
    table["is_complete"] = table["orders"] >= cutoff
    complete = table.loc[table["is_complete"], "month"]
    if complete.empty:
        raise ValueError("No complete month found in the data.")
    return complete.min(), complete.max(), table


def _main_payment(payments: pd.DataFrame) -> pd.DataFrame:
    """Order-level payment summary: total paid, main payment type, installments."""
    totals = payments.groupby("order_id", as_index=False).agg(
        order_revenue=("payment_value", "sum"),
        installments=("payment_installments", "max"),
    )
    main = (
        payments.sort_values(["order_id", "payment_value"], ascending=[True, False])
        .drop_duplicates("order_id")
        .loc[:, ["order_id", "payment_type"]]
    )
    return totals.merge(main, on="order_id", how="left")


def _encode_ids(*tables: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    id_cols = ["order_id", "customer_unique_id", "product_id", "seller_id"]
    out = [t.copy() for t in tables]
    for col in id_cols:
        values = pd.concat([t[col] for t in out if col in t.columns]).dropna().unique()
        codes = {v: i for i, v in enumerate(sorted(values))}
        for t in out:
            if col in t.columns:
                t[col] = t[col].map(codes).astype("int32")
    for t in out:
        for col in (
            "customer_state",
            "seller_state",
            "customer_city",
            "category",
            "category_group",
            "category_en",
            "payment_type",
            "order_status",
            "state",
        ):
            if col in t.columns:
                t[col] = t[col].astype("category")
    return tuple(out)


def build_tables(clean: dict[str, pd.DataFrame]) -> dict[str, object]:
    orders = clean["orders"].merge(clean["customers"], on="customer_id", how="left")

    first_month, last_month, month_table = detect_complete_months(
        orders["order_purchase_timestamp"]
    )
    orders["month"] = orders["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    in_period = orders["month"].between(first_month, last_month)

    # ---- order health (all statuses, complete period) ---------------------------------
    order_status = orders.loc[in_period, ["order_id", "month", "customer_state", "order_status"]]
    order_status = order_status.assign(is_lost=order_status["order_status"].isin(LOST_STATUSES))

    # ---- delivered orders --------------------------------------------------------------
    delivered_all = orders[orders["order_status"] == "delivered"].copy()

    # First purchase over the FULL history, so a 2016 buyer counts as returning in 2017.
    first_purchase = delivered_all.groupby("customer_unique_id")["order_purchase_timestamp"].min()
    delivered_all["is_first_order"] = delivered_all["order_purchase_timestamp"].eq(
        delivered_all["customer_unique_id"].map(first_purchase)
    )
    delivered = delivered_all[delivered_all["month"].between(first_month, last_month)].copy()

    # ---- items ---------------------------------------------------------------------------
    items = (
        clean["items"]
        .merge(clean["products"], on="product_id", how="left")
        .merge(clean["sellers"][["seller_id", "seller_state"]], on="seller_id", how="left")
    )
    items["category_en"] = items["category_en"].fillna("unknown")
    items["item_revenue"] = items["price"] + items["freight_value"]

    item_totals = items.groupby("order_id", as_index=False).agg(
        n_items=("order_item_id", "count"),
        items_value=("item_revenue", "sum"),
        freight_value=("freight_value", "sum"),
    )
    pay = _main_payment(clean["payments"])

    fo = (
        delivered.merge(item_totals, on="order_id", how="left")
        .merge(pay, on="order_id", how="left")
        .merge(clean["reviews"], on="order_id", how="left")
    )
    # One order has no payment record: fall back on the value of its items.
    fo["order_revenue"] = fo["order_revenue"].fillna(fo["items_value"])
    fo["n_items"] = fo["n_items"].fillna(0).astype(int)

    purchase = fo["order_purchase_timestamp"]
    delivered_at = fo["order_delivered_customer_date"]
    estimated = fo["order_estimated_delivery_date"]
    fo["delivery_days"] = (delivered_at - purchase).dt.total_seconds() / 86_400
    fo["delay_days"] = (delivered_at.dt.normalize() - estimated.dt.normalize()).dt.days
    fo["is_late"] = np.where(fo["delay_days"].notna(), fo["delay_days"] > 0, np.nan)

    fact_orders = pd.DataFrame(
        {
            "order_id": fo["order_id"],
            "purchase_ts": purchase,
            "purchase_date": purchase.dt.normalize(),
            "month": fo["month"],
            "customer_unique_id": fo["customer_unique_id"],
            "customer_state": fo["customer_state"],
            "customer_city": fo["customer_city"].str.title(),
            "order_revenue": fo["order_revenue"],
            "n_items": fo["n_items"],
            "freight_value": fo["freight_value"].fillna(0.0),
            "delivered_date": delivered_at,
            "estimated_date": estimated,
            "delivery_days": fo["delivery_days"],
            "delay_days": fo["delay_days"],
            "is_late": fo["is_late"].astype("float"),
            "review_score": fo["review_score"],
            "payment_type": fo["payment_type"].fillna("not_defined"),
            "installments": fo["installments"],
            "is_first_order": fo["is_first_order"],
        }
    )

    # ---- order items (delivered, complete period) ----------------------------------------
    fi = items.merge(
        fact_orders[
            [
                "order_id",
                "purchase_date",
                "month",
                "customer_unique_id",
                "customer_state",
                "customer_city",
                "order_revenue",
            ]
        ],
        on="order_id",
        how="inner",
    ).merge(item_totals[["order_id", "items_value"]], on="order_id", how="left")
    # Allocate the amount actually paid to each item, pro rata of its value, so that
    # category revenue adds up exactly to total revenue.
    share = np.where(fi["items_value"] > 0, fi["item_revenue"] / fi["items_value"], 0.0)
    fi["item_paid"] = fi["order_revenue"] * share

    top = fi.groupby("category_en")["item_paid"].sum().nlargest(TOP_N_CATEGORIES).index.tolist()
    fi["category"] = fi["category_en"].map(category_label)
    fi["category_group"] = np.where(fi["category_en"].isin(top), fi["category"], OTHER)

    fact_order_items = fi[
        [
            "order_id",
            "order_item_id",
            "purchase_date",
            "month",
            "product_id",
            "category_en",
            "category",
            "category_group",
            "seller_id",
            "seller_state",
            "customer_unique_id",
            "customer_state",
            "customer_city",
            "price",
            "freight_value",
            "item_revenue",
            "item_paid",
        ]
    ].reset_index(drop=True)

    # ---- customers ---------------------------------------------------------------------
    dim_customers = (
        fact_orders.sort_values("purchase_ts")
        .groupby("customer_unique_id", as_index=False)
        .agg(
            n_orders=("order_id", "nunique"),
            total_revenue=("order_revenue", "sum"),
            state=("customer_state", "last"),
        )
    )
    dim_customers["first_order_date"] = (
        dim_customers["customer_unique_id"].map(first_purchase).dt.normalize()
    )
    dim_customers = dim_customers[
        ["customer_unique_id", "first_order_date", "n_orders", "total_revenue", "state"]
    ]

    # Long hexadecimal ids are useless in a dashboard and make files 3x larger:
    # replace them by compact integer codes (same code in every table).
    fact_orders, fact_order_items, dim_customers, order_status = _encode_ids(
        fact_orders, fact_order_items, dim_customers, order_status
    )

    excluded = month_table[~month_table["is_complete"]]
    meta = {
        "built_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "first_month": first_month.strftime("%Y-%m"),
        "last_month": last_month.strftime("%Y-%m"),
        "threshold": INCOMPLETE_MONTH_THRESHOLD,
        "median_monthly_orders": int(month_table["orders"].median()),
        "excluded_months": [
            {"month": m.strftime("%Y-%m"), "orders": int(n)}
            for m, n in zip(excluded["month"], excluded["orders"], strict=True)
        ],
        "top_categories": [category_label(c) for c in top],
        "rows": {
            "fact_orders": len(fact_orders),
            "fact_order_items": len(fact_order_items),
            "dim_customers": len(dim_customers),
            "order_status": len(order_status),
        },
    }

    return {
        "fact_orders": fact_orders.reset_index(drop=True),
        "fact_order_items": fact_order_items,
        "dim_customers": dim_customers.reset_index(drop=True),
        "order_status": order_status.reset_index(drop=True),
        "meta": meta,
    }


def save_tables(tables: dict[str, object], out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in tables.items():
        if name == "meta":
            (out_dir / "meta.json").write_text(json.dumps(obj, indent=2))
        else:
            obj.to_parquet(out_dir / f"{name}.parquet", index=False, compression="zstd")
