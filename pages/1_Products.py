"""Products: which categories drive revenue, and at what price and volume."""

from __future__ import annotations

import streamlit as st

from src import charts as C
from src import kpis as K
from src import ui
from src.labels import fmt_money, fmt_pct

ctx = ui.current_context()
ui.page_header(
    "Products",
    "Which product categories bring the money in — and which ones sell on volume or on price.",
    ctx,
)
ui.empty_selection_guard(ctx)

cats = K.category_summary(ctx.items, ctx.orders)

c1, c2, c3, c4 = st.columns(4)
ui.custom_card(c1, "Categories sold", f"{len(cats):,}")
if not cats.empty:
    top = cats.iloc[0]
    ui.custom_card(
        c2, "Top category", str(top["category"]), f"{fmt_pct(top['revenue_share'])} of revenue"
    )
    ui.custom_card(
        c3,
        "Top 5 categories",
        fmt_pct(cats.head(5)["revenue_share"].sum()),
        "share of total revenue",
    )
with c4:
    ui.kpi_cards(ctx, ["freight_share"])

left, right = st.columns([1.05, 1], gap="large")
with left:
    ui.section(
        "Which categories bring the most revenue?",
        "Top 15 categories. Darker bars = customers spend more per order.",
    )
    ui.chart(C.top_categories_bar(cats))
with right:
    ui.section(
        "How is revenue split across categories?", "Each block is sized by its share of revenue."
    )
    ui.chart(C.category_treemap(cats))

ui.section(
    "Volume sellers or premium products?",
    "Each bubble is a category: further right = more orders, higher = pricier items, "
    "bigger = more revenue. Categories with fewer than 10 orders are hidden.",
)
ui.chart(C.category_scatter(cats))

ui.section("All categories at a glance", "Click a column header to sort.")
table = cats.rename(
    columns={
        "category": "Category",
        "revenue": "Revenue",
        "revenue_share": "Share of revenue",
        "orders": "Orders",
        "aov": "Average order",
        "freight_share": "Shipping share",
        "avg_review": "Average review",
    }
)[
    [
        "Category",
        "Revenue",
        "Share of revenue",
        "Orders",
        "Average order",
        "Shipping share",
        "Average review",
    ]
]
table["Share of revenue"] *= 100
table["Shipping share"] *= 100
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    height=460,
    column_config={
        "Revenue": st.column_config.NumberColumn(format="R$ %,.0f"),
        "Share of revenue": st.column_config.ProgressColumn(
            format="%.1f%%", min_value=0, max_value=float(table["Share of revenue"].max() or 1)
        ),
        "Orders": st.column_config.NumberColumn(format="%,d"),
        "Average order": st.column_config.NumberColumn(format="R$ %.2f"),
        "Shipping share": st.column_config.NumberColumn(format="%.1f%%"),
        "Average review": st.column_config.NumberColumn(format="%.2f ★"),
    },
)
if not cats.empty:
    hi_freight = cats[cats["orders"] >= 100].nlargest(1, "freight_share")
    if not hi_freight.empty:
        r = hi_freight.iloc[0]
        st.caption(
            f"Shipping weighs most in **{r['category']}**: {fmt_pct(r['freight_share'])} of what "
            f"customers pay goes to delivery (average order {fmt_money(r['aov'])}). "
            "Bundling or free-shipping thresholds could lift these baskets."
        )
