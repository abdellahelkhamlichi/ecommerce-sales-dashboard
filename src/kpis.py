"""KPI definitions.

Every function is pure: it takes an already-filtered DataFrame (``fact_orders`` /
``fact_order_items`` layout) and returns a number or a small table. No Streamlit here,
so the same numbers feed the dashboard, the Excel export and the tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.labels import WEEKDAYS, state_label

NAN = float("nan")


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else NAN


# ---------------------------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------------------------
def revenue(orders: pd.DataFrame) -> float:
    """Sum of amounts paid for delivered orders."""
    return float(orders["order_revenue"].sum())


def n_orders(orders: pd.DataFrame) -> int:
    """Distinct delivered orders."""
    return int(orders["order_id"].nunique())


def average_order_value(orders: pd.DataFrame) -> float:
    return _safe_div(revenue(orders), n_orders(orders))


def n_customers(orders: pd.DataFrame) -> int:
    return int(orders["customer_unique_id"].nunique())


def repeat_customer_rate(orders: pd.DataFrame) -> float:
    """Share of customers who ordered at least twice in the selected period."""
    per_customer = orders.groupby("customer_unique_id", observed=True)["order_id"].nunique()
    return _safe_div((per_customer >= 2).sum(), len(per_customer))


def freight_share(items: pd.DataFrame) -> float:
    """Shipping cost as a share of what customers pay for items + shipping."""
    return _safe_div(items["freight_value"].sum(), items["item_revenue"].sum())


def on_time_rate(orders: pd.DataFrame) -> float:
    """Orders delivered on or before the promised date / delivered orders with a date."""
    late = orders["is_late"].dropna()
    return _safe_div((late == 0).sum(), len(late))


def average_delivery_days(orders: pd.DataFrame) -> float:
    days = orders["delivery_days"].dropna()
    return float(days.mean()) if len(days) else NAN


def average_review_score(orders: pd.DataFrame) -> float:
    scores = orders["review_score"].dropna()
    return float(scores.mean()) if len(scores) else NAN


def late_review_gap(orders: pd.DataFrame) -> float:
    """Average score of on-time orders minus average score of late orders."""
    on_time = orders.loc[orders["is_late"] == 0, "review_score"].dropna()
    late = orders.loc[orders["is_late"] == 1, "review_score"].dropna()
    if on_time.empty or late.empty:
        return NAN
    return float(on_time.mean() - late.mean())


def lost_order_rate(order_status: pd.DataFrame) -> float:
    """Cancelled or unavailable orders / all orders placed."""
    return _safe_div(order_status["is_lost"].sum(), len(order_status))


def revenue_growth_mom(orders: pd.DataFrame) -> pd.Series:
    """Month-over-month revenue growth, indexed by month (first month is NaN)."""
    monthly = orders.groupby("month")["order_revenue"].sum().sort_index()
    return monthly.pct_change()


def period_growth(first: float, last: float) -> float:
    return _safe_div(last - first, first)


@dataclass(frozen=True)
class KpiSet:
    revenue: float
    orders: int
    aov: float
    customers: int
    repeat_rate: float
    freight_share: float
    on_time_rate: float
    avg_delivery_days: float
    avg_review: float
    late_review_gap: float

    def as_dict(self) -> dict[str, float]:
        return self.__dict__.copy()


def compute_kpis(orders: pd.DataFrame, items: pd.DataFrame) -> KpiSet:
    return KpiSet(
        revenue=revenue(orders),
        orders=n_orders(orders),
        aov=average_order_value(orders),
        customers=n_customers(orders),
        repeat_rate=repeat_customer_rate(orders),
        freight_share=freight_share(items),
        on_time_rate=on_time_rate(orders),
        avg_delivery_days=average_delivery_days(orders),
        avg_review=average_review_score(orders),
        late_review_gap=late_review_gap(orders),
    )


def relative_change(current: float, previous: float) -> float:
    """(current - previous) / previous; NaN when there is nothing to compare with."""
    if previous is None or not np.isfinite(previous) or previous == 0:
        return NAN
    if current is None or not np.isfinite(current):
        return NAN
    return (current - previous) / abs(previous)


# ---------------------------------------------------------------------------------------
# Tables behind the charts
# ---------------------------------------------------------------------------------------
def monthly_summary(orders: pd.DataFrame) -> pd.DataFrame:
    """One row per month: revenue, orders, AOV, MoM revenue growth, on-time rate."""
    g = orders.groupby("month")
    out = pd.DataFrame(
        {
            "revenue": g["order_revenue"].sum(),
            "orders": g["order_id"].nunique(),
            "customers": g["customer_unique_id"].nunique(),
            "on_time_rate": g["is_late"].apply(
                lambda s: _safe_div((s.dropna() == 0).sum(), s.notna().sum())
            ),
            "avg_review": g["review_score"].mean(),
        }
    ).sort_index()
    out["aov"] = out["revenue"] / out["orders"]
    out["revenue_growth"] = out["revenue"].pct_change()
    return out.reset_index()


def revenue_by_weekday(orders: pd.DataFrame) -> pd.DataFrame:
    wd = orders["purchase_ts"].dt.dayofweek
    out = orders.groupby(wd)["order_revenue"].agg(["sum", "count"]).reindex(range(7), fill_value=0)
    return pd.DataFrame(
        {"weekday": WEEKDAYS, "revenue": out["sum"].to_numpy(), "orders": out["count"].to_numpy()}
    )


def revenue_by_hour(orders: pd.DataFrame) -> pd.DataFrame:
    hr = orders["purchase_ts"].dt.hour
    out = orders.groupby(hr)["order_revenue"].agg(["sum", "count"]).reindex(range(24), fill_value=0)
    return pd.DataFrame(
        {"hour": range(24), "revenue": out["sum"].to_numpy(), "orders": out["count"].to_numpy()}
    )


def category_summary(items: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Category table: revenue, orders, AOV, average price, freight share, avg review."""
    if items.empty:
        return pd.DataFrame(
            columns=[
                "category",
                "revenue",
                "orders",
                "aov",
                "avg_price",
                "freight_share",
                "avg_review",
                "revenue_share",
            ]
        )
    reviews = orders[["order_id", "review_score"]]
    g = items.groupby("category", observed=True)
    out = pd.DataFrame(
        {
            "revenue": g["item_paid"].sum(),
            "orders": g["order_id"].nunique(),
            "avg_price": g["price"].mean(),
            "freight_share": g["freight_value"].sum() / g["item_revenue"].sum(),
        }
    )
    per_cat_order = items[["category", "order_id"]].drop_duplicates().merge(reviews, on="order_id")
    out["avg_review"] = per_cat_order.groupby("category", observed=True)["review_score"].mean()
    out["aov"] = out["revenue"] / out["orders"]
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    out = out[out["orders"] > 0].sort_values("revenue", ascending=False)
    return out.reset_index()[
        [
            "category",
            "revenue",
            "orders",
            "aov",
            "avg_price",
            "freight_share",
            "avg_review",
            "revenue_share",
        ]
    ]


def state_summary(orders: pd.DataFrame) -> pd.DataFrame:
    """Per customer state: revenue, orders, customers, AOV, on-time rate, delivery, review."""
    g = orders.groupby("customer_state", observed=True)
    out = pd.DataFrame(
        {
            "revenue": g["order_revenue"].sum(),
            "orders": g["order_id"].nunique(),
            "customers": g["customer_unique_id"].nunique(),
            "on_time_rate": g["is_late"].apply(
                lambda s: _safe_div((s.dropna() == 0).sum(), s.notna().sum())
            ),
            "avg_delivery_days": g["delivery_days"].mean(),
            "avg_review": g["review_score"].mean(),
        }
    )
    out = out[out["orders"] > 0]
    out["aov"] = out["revenue"] / out["orders"]
    out["revenue_share"] = out["revenue"] / out["revenue"].sum()
    out = out.sort_values("revenue", ascending=False).reset_index()
    out = out.rename(columns={"customer_state": "state_code"})
    out.insert(1, "state", out["state_code"].astype(str).map(state_label))
    return out


def top_cities(orders: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    g = orders.groupby(["customer_city", "customer_state"], observed=True)
    out = pd.DataFrame({"revenue": g["order_revenue"].sum(), "orders": g["order_id"].nunique()})
    out = out[out["orders"] > 0].nlargest(n, "revenue").reset_index()
    out["label"] = out["customer_city"].astype(str) + " (" + out["customer_state"].astype(str) + ")"
    return out


def new_vs_returning(orders: pd.DataFrame) -> pd.DataFrame:
    """Customers per month split by first-ever purchase vs. returning."""
    df = orders.assign(
        customer_type=np.where(orders["is_first_order"], "New customers", "Returning customers")
    )
    out = (
        df.groupby(["month", "customer_type"])["customer_unique_id"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=["New customers", "Returning customers"], fill_value=0)
        .sort_index()
    )
    return out.reset_index()


def on_time_by_lateness_review(orders: pd.DataFrame) -> pd.DataFrame:
    """Average review score for on-time vs. late orders."""
    df = orders.dropna(subset=["is_late", "review_score"])
    out = df.groupby("is_late")["review_score"].agg(["mean", "count"])
    labels = {0.0: "On time", 1.0: "Late"}
    out = out.rename(index=labels).reindex(["On time", "Late"])
    return out.reset_index(names="delivery").rename(
        columns={"mean": "avg_review", "count": "orders"}
    )


def review_by_delay_bucket(orders: pd.DataFrame) -> pd.DataFrame:
    """Average review by how late (or early) the delivery was."""
    df = orders.dropna(subset=["delay_days", "review_score"])
    bins = [-np.inf, -7, 0, 3, 7, 14, np.inf]
    labels = [
        "7+ days<br>early",
        "0–6 days<br>early",
        "1–3 days<br>late",
        "4–7 days<br>late",
        "8–14 days<br>late",
        "15+ days<br>late",
    ]
    bucket = pd.cut(df["delay_days"], bins=bins, labels=labels, right=True)
    out = df.groupby(bucket, observed=False)["review_score"].agg(["mean", "count"])
    return out.reset_index(names="bucket").rename(columns={"mean": "avg_review", "count": "orders"})
