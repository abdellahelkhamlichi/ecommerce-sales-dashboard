"""Delivery & satisfaction: how fast orders arrive and how much delays hurt reviews."""

from __future__ import annotations

import streamlit as st

from src import charts as C
from src import kpis as K
from src import ui
from src.labels import fmt_pct

ctx = ui.current_context()
ui.page_header(
    "Delivery & Satisfaction",
    "How fast orders arrive, where delivery goes wrong, and what late orders do to reviews.",
    ctx,
)
ui.empty_selection_guard(ctx)

cols = st.columns(5)
ui.kpi_cards(
    ctx, ["avg_delivery_days", "on_time_rate", "avg_review", "late_review_gap"], cols=cols[:4]
)
c1 = cols[4]
lost = K.lost_order_rate(ctx.status)
note = "orders cancelled or unavailable"
if ctx.prev_status is not None and len(ctx.prev_status):
    cmp_lost = K.lost_order_rate(ctx.cmp_status if ctx.cmp_status is not None else ctx.status)
    diff = (cmp_lost - K.lost_order_rate(ctx.prev_status)) * 100
    label = ctx.prev_label if ctx.prev_label.startswith("last ") else f"vs {ctx.prev_label}"
    color = ui.ACCENT if diff <= 0 else ui.RED
    note = (
        f'<b style="color:{color}">{"▲" if diff > 0 else "▼"} {diff:+.1f} pts</b> '
        f"{label} · cancelled or unavailable"
    )

states = K.state_summary(ctx.orders)
monthly = K.monthly_summary(ctx.orders)
review_split = K.on_time_by_lateness_review(ctx.orders)

ui.section(
    "Do late deliveries hurt customer satisfaction?",
    "Average review score (1 to 5 stars) for orders delivered on time vs late.",
)
left, right = st.columns([1, 1.3], gap="large")
with left:
    ui.chart(C.review_on_time_vs_late(review_split))
with right:
    ui.chart(C.review_by_delay(K.review_by_delay_bucket(ctx.orders)))
gap = ctx.kpis.late_review_gap
if review_split["orders"].notna().all():
    late_share = 1 - ctx.kpis.on_time_rate
    st.caption(
        f"Only {fmt_pct(late_share)} of orders arrive late, but those orders lose "
        f"**{gap:.1f} stars** on average. The longer the delay, the worse the review — "
        "reliable delivery is a direct lever on customer satisfaction."
    )

left, right = st.columns(2, gap="large")
with left:
    ui.section(
        "How long do customers wait?",
        "Number of orders by days between purchase and delivery. Red = 30 days or more.",
    )
    ui.chart(C.delivery_histogram(ctx.orders))
with right:
    ui.section("Is delivery getting better?", "Share of orders delivered on time, each month.")
    ui.chart(C.monthly_on_time_line(monthly))

ui.section(
    "Where does delivery go wrong?",
    "On-time rate by customer state (states with 100+ orders), worst first. "
    "The 5 weakest states are in red.",
)
ui.chart(C.on_time_by_state_bar(states, ctx.kpis.on_time_rate))

ui.custom_card(c1, "Lost orders", fmt_pct(lost), note)
