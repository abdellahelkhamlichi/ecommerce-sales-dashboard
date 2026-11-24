"""Global filters (date range, states, categories) applied identically on every page."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Filters:
    start: pd.Timestamp  # first month included (month start)
    end: pd.Timestamp  # last month included (month start)
    states: tuple[str, ...] = field(default_factory=tuple)  # empty = all
    categories: tuple[str, ...] = field(default_factory=tuple)  # category_group; empty = all

    @property
    def n_months(self) -> int:
        return (self.end.year - self.start.year) * 12 + self.end.month - self.start.month + 1

    def previous(self) -> Filters:
        """Same-length period immediately before this one (same states / categories)."""
        n = self.n_months
        return Filters(
            start=self.start - pd.DateOffset(months=n),
            end=self.start - pd.DateOffset(months=1),
            states=self.states,
            categories=self.categories,
        )


def apply_filters(
    orders: pd.DataFrame, items: pd.DataFrame, f: Filters
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (orders, items) restricted to the filters.

    With a category filter, an order is kept when it contains at least one item of the
    selected categories, and its revenue / freight / item count are restated to those
    items only. Revenue therefore always equals the sum of the category revenues shown
    on the Products page.
    """
    o_mask = orders["month"].between(f.start, f.end)
    i_mask = items["month"].between(f.start, f.end)
    if f.states:
        o_mask &= orders["customer_state"].isin(f.states)
        i_mask &= items["customer_state"].isin(f.states)
    o = orders[o_mask]
    i = items[i_mask]

    if f.categories:
        i = i[i["category_group"].isin(f.categories)]
        per_order = i.groupby("order_id").agg(
            order_revenue=("item_paid", "sum"),
            freight_value=("freight_value", "sum"),
            n_items=("order_item_id", "count"),
        )
        o = o[o["order_id"].isin(per_order.index)].drop(
            columns=["order_revenue", "freight_value", "n_items"]
        )
        o = o.join(per_order, on="order_id")
    return o, i


def filter_order_status(status: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Order-health table (all statuses). Category filter does not apply (no items)."""
    mask = status["month"].between(f.start, f.end)
    if f.states:
        mask &= status["customer_state"].isin(f.states)
    return status[mask]
