"""Streamlit entry point: global filters, navigation and the Overview page.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from src import charts as C
from src import kpis as K
from src import ui

st.set_page_config(
    page_title="Sales Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def overview() -> None:
    ctx = ui.current_context()
    ui.page_header(
        "Sales Performance Overview",
        "Two years of orders from a Brazilian online marketplace: what sells, when, "
        "and how well it is delivered.",
        ctx,
    )
    ui.empty_selection_guard(ctx)

    ui.kpi_cards(ctx, ["revenue", "orders", "aov", "customers", "on_time_rate"])
    ui.insights_box(ui.overview_insights(ctx))

    monthly = K.monthly_summary(ctx.orders)
    ui.section(
        "Is the business growing?",
        "Revenue and number of orders each month. Hover a month for its growth "
        "vs the previous month; red bars flag a drop of more than 10%.",
    )
    ui.chart(C.monthly_trend(monthly))

    left, right = st.columns(2, gap="large")
    with left:
        ui.section(
            "Which days bring the most revenue?",
            "Total revenue by day of the week; the best day is highlighted.",
        )
        ui.chart(C.weekday_bars(K.revenue_by_weekday(ctx.orders)))
    with right:
        ui.section(
            "At what time do customers buy?", "Total revenue by hour of purchase (Brasília time)."
        )
        ui.chart(C.hour_bars(K.revenue_by_hour(ctx.orders)))


pages = [
    st.Page(overview, title="Overview", icon="📊", default=True),
    st.Page("pages/1_Products.py", title="Products", icon="🛍️", url_path="products"),
    st.Page(
        "pages/2_Customers_and_Regions.py",
        title="Customers & Regions",
        icon="🗺️",
        url_path="customers",
    ),
    st.Page(
        "pages/3_Delivery_and_Satisfaction.py",
        title="Delivery & Satisfaction",
        icon="🚚",
        url_path="delivery",
    ),
]
nav = st.navigation(pages)
st.session_state["filters"] = ui.render_sidebar()
nav.run()
