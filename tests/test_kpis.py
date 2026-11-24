"""Unit tests for KPIs, filters, labels and the incomplete-month rule.

The small hand-made tables below make every expected value checkable by hand.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import kpis
from src.build import detect_complete_months
from src.filters import Filters, apply_filters
from src.labels import category_label, fmt_money, fmt_pct

M1, M2, M3 = pd.Timestamp("2018-01-01"), pd.Timestamp("2018-02-01"), pd.Timestamp("2018-03-01")


@pytest.fixture
def orders() -> pd.DataFrame:
    # 5 orders, 3 customers. Customer 1 orders twice (repeat), customer 2 three times.
    return pd.DataFrame(
        {
            "order_id": [1, 2, 3, 4, 5],
            "customer_unique_id": [1, 1, 2, 2, 3],
            "month": [M1, M1, M2, M2, M3],
            "purchase_ts": pd.to_datetime(
                [
                    "2018-01-01 10:00",
                    "2018-01-02 10:00",
                    "2018-02-05 21:00",
                    "2018-02-06 21:00",
                    "2018-03-07 09:00",
                ]
            ),
            "customer_state": ["SP", "SP", "RJ", "RJ", "MG"],
            "customer_city": ["Sao Paulo", "Sao Paulo", "Rio", "Rio", "Bh"],
            "order_revenue": [100.0, 50.0, 200.0, 150.0, 500.0],
            "freight_value": [10.0, 5.0, 20.0, 15.0, 50.0],
            "n_items": [1, 1, 1, 1, 2],
            "delivery_days": [5.0, 10.0, 7.0, np.nan, 20.0],
            "delay_days": [-3.0, 0.0, -1.0, np.nan, 4.0],
            "is_late": [0.0, 0.0, 0.0, np.nan, 1.0],
            "review_score": [5.0, 4.0, 5.0, np.nan, 1.0],
            "is_first_order": [True, False, True, False, True],
        }
    )


@pytest.fixture
def items() -> pd.DataFrame:
    # Order 5 has two items in two categories.
    return pd.DataFrame(
        {
            "order_id": [1, 2, 3, 4, 5, 5],
            "order_item_id": [1, 1, 1, 1, 1, 2],
            "month": [M1, M1, M2, M2, M3, M3],
            "customer_state": ["SP", "SP", "RJ", "RJ", "MG", "MG"],
            "category": ["Toys", "Toys", "Books", "Books", "Toys", "Books"],
            "category_group": ["Toys", "Toys", "Books", "Books", "Toys", "Books"],
            "price": [90.0, 45.0, 180.0, 135.0, 300.0, 150.0],
            "freight_value": [10.0, 5.0, 20.0, 15.0, 30.0, 20.0],
            "item_revenue": [100.0, 50.0, 200.0, 150.0, 330.0, 170.0],
            "item_paid": [100.0, 50.0, 200.0, 150.0, 330.0, 170.0],
        }
    )


# ---- headline KPIs ---------------------------------------------------------------------
def test_revenue(orders):
    assert kpis.revenue(orders) == 1000.0


def test_orders(orders):
    assert kpis.n_orders(orders) == 5


def test_average_order_value(orders):
    assert kpis.average_order_value(orders) == pytest.approx(200.0)


def test_customers(orders):
    assert kpis.n_customers(orders) == 3


def test_repeat_customer_rate(orders):
    # customers 1 and 2 ordered twice, customer 3 once -> 2/3
    assert kpis.repeat_customer_rate(orders) == pytest.approx(2 / 3)


def test_revenue_growth_mom(orders):
    growth = kpis.revenue_growth_mom(orders)
    assert math.isnan(growth.iloc[0])
    assert growth.loc[M2] == pytest.approx((350 - 150) / 150)
    assert growth.loc[M3] == pytest.approx((500 - 350) / 350)


def test_freight_share(items):
    assert kpis.freight_share(items) == pytest.approx(100 / 1000)


def test_on_time_rate_ignores_orders_without_date(orders):
    # 4 orders with a delivery date, 3 on time (delay 0 counts as on time)
    assert kpis.on_time_rate(orders) == pytest.approx(3 / 4)


def test_average_delivery_days(orders):
    assert kpis.average_delivery_days(orders) == pytest.approx((5 + 10 + 7 + 20) / 4)


def test_average_review_score(orders):
    assert kpis.average_review_score(orders) == pytest.approx((5 + 4 + 5 + 1) / 4)


def test_late_review_gap(orders):
    # on time: (5+4+5)/3 = 4.667 ; late: 1 -> gap 3.667
    assert kpis.late_review_gap(orders) == pytest.approx(14 / 3 - 1)


def test_late_review_gap_without_late_orders(orders):
    assert math.isnan(kpis.late_review_gap(orders[orders["is_late"] == 0]))


def test_empty_selection_returns_nan_not_error(orders, items):
    k = kpis.compute_kpis(orders.iloc[0:0], items.iloc[0:0])
    assert k.revenue == 0 and k.orders == 0
    assert math.isnan(k.aov) and math.isnan(k.on_time_rate) and math.isnan(k.repeat_rate)


def test_lost_order_rate():
    status = pd.DataFrame({"is_lost": [True, False, False, False]})
    assert kpis.lost_order_rate(status) == 0.25


def test_relative_change():
    assert kpis.relative_change(120, 100) == pytest.approx(0.2)
    assert math.isnan(kpis.relative_change(120, 0))
    assert math.isnan(kpis.relative_change(120, float("nan")))


# ---- tables ---------------------------------------------------------------------------
def test_monthly_summary(orders):
    m = kpis.monthly_summary(orders)
    assert m["revenue"].tolist() == [150.0, 350.0, 500.0]
    assert m["orders"].tolist() == [2, 2, 1]
    assert m["aov"].tolist() == [75.0, 175.0, 500.0]


def test_category_summary_adds_up_to_revenue(orders, items):
    cats = kpis.category_summary(items, orders)
    assert cats["revenue"].sum() == pytest.approx(kpis.revenue(orders))
    toys = cats.set_index("category").loc["Toys"]
    assert toys["revenue"] == 480.0 and toys["orders"] == 3
    assert cats["revenue_share"].sum() == pytest.approx(1.0)


def test_state_summary(orders):
    s = kpis.state_summary(orders).set_index("state_code")
    assert s.loc["MG", "revenue"] == 500.0
    assert s.loc["SP", "state"] == "São Paulo"
    assert s.loc["SP", "on_time_rate"] == 1.0


def test_new_vs_returning(orders):
    nr = kpis.new_vs_returning(orders).set_index("month")
    assert nr.loc[M1, "New customers"] == 1 and nr.loc[M1, "Returning customers"] == 1


def test_weekday_and_hour_cover_all_slots(orders):
    assert len(kpis.revenue_by_weekday(orders)) == 7
    hours = kpis.revenue_by_hour(orders)
    assert len(hours) == 24 and hours["revenue"].sum() == pytest.approx(1000.0)


# ---- filters ---------------------------------------------------------------------------
def test_filter_by_date_and_state(orders, items):
    f = Filters(start=M1, end=M2, states=("RJ",))
    o, i = apply_filters(orders, items, f)
    assert set(o["order_id"]) == {3, 4}
    assert set(i["order_id"]) == {3, 4}


def test_category_filter_restates_order_revenue(orders, items):
    f = Filters(start=M1, end=M3, categories=("Books",))
    o, i = apply_filters(orders, items, f)
    assert set(o["order_id"]) == {3, 4, 5}
    # order 5 keeps only its Books item (170), not the full 500
    assert o.set_index("order_id").loc[5, "order_revenue"] == 170.0
    assert kpis.revenue(o) == pytest.approx(i["item_paid"].sum())


def test_previous_period():
    f = Filters(start=pd.Timestamp("2018-03-01"), end=pd.Timestamp("2018-05-01"))
    p = f.previous()
    assert (p.start, p.end) == (pd.Timestamp("2017-12-01"), pd.Timestamp("2018-02-01"))
    assert p.n_months == f.n_months == 3


# ---- incomplete months -----------------------------------------------------------------
def test_detect_complete_months_drops_sparse_edges():
    counts = {
        "2016-09": 4,
        "2016-10": 50,
        "2017-01": 800,
        "2017-02": 5000,
        "2017-03": 5200,
        "2017-04": 5100,
        "2017-05": 16,
    }
    ts = pd.Series(pd.to_datetime([m for m, n in counts.items() for _ in range(n)], format="%Y-%m"))
    first, last, table = detect_complete_months(ts)
    assert first == pd.Timestamp("2017-01-01")
    assert last == pd.Timestamp("2017-04-01")
    assert table["is_complete"].sum() == 4


# ---- labels ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [(1_234_567, "R$ 1.2M"), (154_321, "R$ 154K"), (8_460, "R$ 8.5K"), (860, "R$ 860")],
)
def test_fmt_money(value, expected):
    assert fmt_money(value) == expected


def test_fmt_pct():
    assert fmt_pct(0.1234) == "12.3%"
    assert fmt_pct(0.05, signed=True) == "+5.0%"


def test_category_label():
    assert category_label("health_beauty") == "Health & Beauty"
    assert category_label("garden_tools") == "Garden Tools"


# ---- consistency on the real processed data (skipped if not built) -------------------
PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


@pytest.mark.skipif(not (PROCESSED / "fact_orders.parquet").exists(), reason="data not built")
def test_real_data_is_consistent():
    o = pd.read_parquet(PROCESSED / "fact_orders.parquet")
    i = pd.read_parquet(PROCESSED / "fact_order_items.parquet")
    assert o["order_id"].is_unique
    assert kpis.revenue(o) == pytest.approx(i["item_paid"].sum(), rel=1e-9)
    assert kpis.category_summary(i, o)["revenue"].sum() == pytest.approx(kpis.revenue(o))
    assert kpis.state_summary(o)["revenue"].sum() == pytest.approx(kpis.revenue(o))
    assert 0.85 < kpis.on_time_rate(o) < 0.98
