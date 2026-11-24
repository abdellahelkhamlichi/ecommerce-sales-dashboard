"""Read the raw Olist CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

RAW_FILES: dict[str, str] = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# Only the columns the dashboard needs: keeps memory low and the build fast.
USECOLS: dict[str, list[str]] = {
    "orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "items": ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    "payments": [
        "order_id",
        "payment_sequential",
        "payment_type",
        "payment_installments",
        "payment_value",
    ],
    "reviews": ["review_id", "order_id", "review_score", "review_answer_timestamp"],
    "customers": ["customer_id", "customer_unique_id", "customer_city", "customer_state"],
    "products": ["product_id", "product_category_name"],
    "sellers": ["seller_id", "seller_city", "seller_state"],
    "category_translation": ["product_category_name", "product_category_name_english"],
}


def load_raw(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Read every raw CSV into a dict of DataFrames keyed by short table name."""
    missing = [f for f in RAW_FILES.values() if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw files in {raw_dir}: {', '.join(missing)}.\n"
            "Download the 'Brazilian E-Commerce Public Dataset by Olist' from Kaggle "
            "and unzip the CSVs into data/raw/."
        )
    return {
        name: pd.read_csv(raw_dir / filename, usecols=USECOLS[name])
        for name, filename in RAW_FILES.items()
    }
