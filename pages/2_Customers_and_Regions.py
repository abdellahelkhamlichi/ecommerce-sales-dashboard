"""Customers & regions: where revenue comes from and whether customers come back."""

from __future__ import annotations

import streamlit as st

from src import charts as C
from src import kpis as K
from src import ui
from src.labels import fmt_money, fmt_pct

ctx = ui.current_context()
ui.page_header(
    "Customers & Regions",
    "Where the customers are, which cities matter most, and how many come back.",
    ctx,
)
ui.empty_selection_guard(ctx)

states = K.state_summary(ctx.orders)
ui.kpi_cards(ctx, ["customers", "repeat_rate", "aov", "revenue"])

left, right = st.columns([1.1, 1], gap="large")
with left:
    ui.section(
        "Which states bring the most revenue?", "Darker = more revenue. Hover a state for details."
    )
    ui.chart(C.state_map(states))
with right:
    ui.section("Which cities are the biggest markets?", "Top 10 cities by revenue.")
    ui.chart(C.top_cities_bar(K.top_cities(ctx.orders)))
    if len(states) >= 3:
        top3 = states.head(3)
        st.caption(
            f"**{', '.join(top3['state'])}** together bring "
            f"**{fmt_pct(top3['revenue_share'].sum())}** of revenue — "
            f"{top3.iloc[0]['state']} alone: {fmt_money(top3.iloc[0]['revenue'])}."
        )

ui.section(
    "Are we winning new customers or keeping old ones?",
    "Buyers each month, split between first-time and returning customers.",
)
chart_col, text_col = st.columns([2.2, 1], gap="large")
with chart_col:
    ui.chart(C.new_vs_returning_bar(K.new_vs_returning(ctx.orders)))
with text_col:
    rate = ctx.kpis.repeat_rate
    per_100 = max(1, round(rate * 100))
    noun = "customer" if per_100 == 1 else "customers"
    st.markdown(
        f"""<div class="explain">
<b>Repeat customer rate: {fmt_pct(rate)}</b><br><br>
Only about <b>{per_100} {noun} in 100</b> ordered more than once in this
period. Almost all revenue comes from first-time buyers, so every sale costs a new
acquisition.<br><br>
<b>Why it matters:</b> winning a new customer typically costs several times more than
keeping one. Even doubling the repeat rate — with follow-up emails, a loyalty discount or
reminders for consumable products — would add revenue without extra advertising spend.
</div>""",
        unsafe_allow_html=True,
    )
