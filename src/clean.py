"""Cleaning: types, duplicates, missing values, one review per order.

Every step is logged in a small cleaning report (rows before -> after).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

ORDER_DATE_COLS = [
    "order_purchase_timestamp",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

# Two categories are missing from Olist's translation file.
EXTRA_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_appliances",
}

# Statuses that mean the sale never happened ("order health" metric).
LOST_STATUSES = ("canceled", "unavailable")


@dataclass
class CleaningReport:
    """Collects row counts before and after every cleaning step."""

    lines: list[tuple[str, str, int, int]] = field(default_factory=list)

    def log(self, table: str, step: str, before: int, after: int) -> None:
        self.lines.append((table, step, before, after))

    def __str__(self) -> str:
        header = f"{'table':<12} {'step':<52} {'before':>9} {'after':>9} {'removed':>8}"
        rows = [header, "-" * len(header)]
        for table, step, before, after in self.lines:
            rows.append(f"{table:<12} {step:<52} {before:>9,} {after:>9,} {before - after:>8,}")
        return "\n".join(rows)


def _drop_duplicates(df: pd.DataFrame, name: str, report: CleaningReport) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates()
    report.log(name, "drop exact duplicates", before, len(df))
    return df


def clean_orders(orders: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    df = _drop_duplicates(orders, "orders", report)
    for col in ORDER_DATE_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["order_purchase_timestamp"])
    report.log("orders", "drop orders without a purchase date", before, len(df))
    return df.reset_index(drop=True)


def clean_items(items: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    df = _drop_duplicates(items, "items", report)
    before = len(df)
    df = df[(df["price"] >= 0) & (df["freight_value"] >= 0)]
    report.log("items", "drop negative prices / freight", before, len(df))
    return df.reset_index(drop=True)


def clean_payments(payments: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    df = _drop_duplicates(payments, "payments", report)
    before = len(df)
    df = df[df["payment_value"] >= 0]
    report.log("payments", "drop negative payments", before, len(df))
    return df.reset_index(drop=True)


def clean_reviews(reviews: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    """Keep only the latest review for each order."""
    df = _drop_duplicates(reviews, "reviews", report)
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    before = len(df)
    df = (
        df.sort_values(["order_id", "review_answer_timestamp"])
        .drop_duplicates("order_id", keep="last")
        .loc[:, ["order_id", "review_score"]]
    )
    report.log("reviews", "keep latest review per order", before, len(df))
    return df.reset_index(drop=True)


def clean_products(
    products: pd.DataFrame, translation: pd.DataFrame, report: CleaningReport
) -> pd.DataFrame:
    """Attach the English category name; missing categories become 'unknown'."""
    df = _drop_duplicates(products, "products", report)
    mapping = dict(
        zip(
            translation["product_category_name"],
            translation["product_category_name_english"],
            strict=True,
        )
    )
    mapping.update(EXTRA_TRANSLATIONS)
    n_missing = int(df["product_category_name"].isna().sum())
    df["category_en"] = df["product_category_name"].map(mapping).fillna("unknown")
    step = f"fill missing category with 'unknown' ({n_missing:,})"
    report.log("products", step, len(df), len(df))
    return df.loc[:, ["product_id", "category_en"]].reset_index(drop=True)


def clean_all(raw: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], CleaningReport]:
    report = CleaningReport()
    clean = {
        "orders": clean_orders(raw["orders"].copy(), report),
        "items": clean_items(raw["items"].copy(), report),
        "payments": clean_payments(raw["payments"].copy(), report),
        "reviews": clean_reviews(raw["reviews"].copy(), report),
        "customers": _drop_duplicates(raw["customers"].copy(), "customers", report),
        "products": clean_products(raw["products"].copy(), raw["category_translation"], report),
        "sellers": _drop_duplicates(raw["sellers"].copy(), "sellers", report),
    }
    return clean, report
