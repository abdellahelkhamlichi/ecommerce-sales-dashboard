"""Streamlit glue shared by every page: cached data, global filters, KPI cards, insights."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src import kpis as K
from src.export import build_excel
from src.filters import Filters, apply_filters, filter_order_status
from src.labels import (
    OTHER,
    fmt_days,
    fmt_int,
    fmt_money,
    fmt_money_exact,
    fmt_month,
    fmt_pct,
    fmt_score,
    state_label,
)

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

ACCENT, RED, MUTED = "#1F6FEB", "#D1242F", "#59636E"


# ---------------------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading sales data…")
def load_data() -> dict[str, object]:
    if not (PROCESSED / "fact_orders.parquet").exists():
        st.error("Processed data not found. Run `python scripts/build_data.py` first.")
        st.stop()
    return {
        "orders": pd.read_parquet(PROCESSED / "fact_orders.parquet"),
        "items": pd.read_parquet(PROCESSED / "fact_order_items.parquet"),
        "status": pd.read_parquet(PROCESSED / "order_status.parquet"),
        "meta": json.loads((PROCESSED / "meta.json").read_text()),
    }


@dataclass
class Context:
    filters: Filters
    orders: pd.DataFrame
    items: pd.DataFrame
    status: pd.DataFrame
    kpis: K.KpiSet
    prev_kpis: K.KpiSet | None
    prev_label: str
    prev_status: pd.DataFrame | None
    meta: dict
    # What the delta compares. Normally the selected period itself vs the previous one of
    # the same length; when the data has no earlier period (e.g. the full history is
    # selected) we compare the latest months of the selection with the months before.
    cmp_kpis: K.KpiSet | None = None
    cmp_status: pd.DataFrame | None = None


def _period_label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    if start == end:
        return fmt_month(start)
    if start.year == end.year:
        return f"{start.strftime('%b')}–{end.strftime('%b %Y')}"
    return f"{fmt_month(start)} – {fmt_month(end)}"


def build_context(f: Filters) -> Context:
    data = load_data()
    orders, items, status = apply_filters(data["orders"], data["items"], f) + (
        filter_order_status(data["status"], f),
    )
    first_month = pd.Timestamp(data["meta"]["first_month"])
    kpi_now = K.compute_kpis(orders, items)
    prev_f = f.previous()
    cmp_kpis, cmp_status = kpi_now, status
    if prev_f.start >= first_month:
        compare_f = prev_f
        prev_label = _period_label(prev_f.start, prev_f.end)
    elif f.n_months >= 4:
        # No earlier data: compare the recent half (max 6 months) with the half before it.
        n = min(6, f.n_months // 2)
        recent = Filters(f.end - pd.DateOffset(months=n - 1), f.end, f.states, f.categories)
        compare_f = recent.previous()
        ro, ri = apply_filters(data["orders"], data["items"], recent)
        cmp_kpis = K.compute_kpis(ro, ri)
        cmp_status = filter_order_status(data["status"], recent)
        prev_label = f"last {n} months vs the {n} before"
    else:
        compare_f, prev_label = None, ""
    if compare_f is not None:
        po, pi = apply_filters(data["orders"], data["items"], compare_f)
        prev_kpis = K.compute_kpis(po, pi)
        prev_status = filter_order_status(data["status"], compare_f)
    else:
        prev_kpis, prev_status = None, None
    return Context(
        f,
        orders,
        items,
        status,
        kpi_now,
        prev_kpis,
        prev_label,
        prev_status,
        data["meta"],
        cmp_kpis,
        cmp_status,
    )


# ---------------------------------------------------------------------------------------
# Global sidebar filters (rendered once by app.py, shared by every page)
# ---------------------------------------------------------------------------------------
def _month_options(meta: dict) -> list[pd.Timestamp]:
    return list(pd.date_range(meta["first_month"], meta["last_month"], freq="MS"))


def render_sidebar() -> Filters:
    data = load_data()
    meta, orders, items = data["meta"], data["orders"], data["items"]
    months = _month_options(meta)

    st.sidebar.markdown("### Filters")
    start, end = st.sidebar.select_slider(
        "Period",
        options=months,
        value=(months[0], months[-1]),
        format_func=fmt_month,
        key="flt_period",
        help="Only complete months are available.",
    )
    state_rev = orders.groupby("customer_state", observed=True)["order_revenue"].sum()
    state_options = state_rev.sort_values(ascending=False).index.astype(str).tolist()
    states = st.sidebar.multiselect(
        "Customer state",
        options=state_options,
        format_func=lambda s: f"{state_label(s)} ({s})",
        placeholder="All states",
        key="flt_states",
    )
    cat_rev = items.groupby("category_group", observed=True)["item_paid"].sum()
    cat_options = [c for c in cat_rev.sort_values(ascending=False).index.astype(str) if c != OTHER]
    categories = st.sidebar.multiselect(
        "Product category",
        options=[*cat_options, OTHER],
        placeholder="All categories",
        key="flt_categories",
        help=f"The {len(cat_options)} largest categories; the rest are grouped under “Other”.",
    )
    f = Filters(
        start=pd.Timestamp(start),
        end=pd.Timestamp(end),
        states=tuple(states),
        categories=tuple(categories),
    )

    st.sidebar.divider()
    st.sidebar.download_button(
        "⬇  Download Excel summary",
        data=excel_bytes(f),
        file_name=f"sales_summary_{f.start:%Y%m}_{f.end:%Y%m}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        type="primary",
    )
    st.sidebar.caption(
        "KPIs, monthly trend, categories and states for the current filters, in one workbook."
    )
    return f


def filter_description(f: Filters) -> str:
    parts = [f"Period: {_period_label(f.start, f.end)}"]
    parts.append("States: " + (", ".join(state_label(s) for s in f.states) if f.states else "all"))
    parts.append("Categories: " + (", ".join(f.categories) if f.categories else "all"))
    return " · ".join(parts)


def excluded_description(meta: dict) -> str:
    months = [pd.Timestamp(m["month"]) for m in meta["excluded_months"]]
    return (
        f"Data covers {fmt_month(pd.Timestamp(meta['first_month']))} – "
        f"{fmt_month(pd.Timestamp(meta['last_month']))}. Left out as incomplete "
        f"(under 10% of a normal month's orders): {', '.join(fmt_month(m) for m in months)}."
    )


@st.cache_data(show_spinner=False, max_entries=32)
def excel_bytes(f: Filters) -> bytes:
    ctx = build_context(f)
    # The workbook only compares with a true previous period of the same length.
    same_length_prev = ctx.prev_kpis if not ctx.prev_label.startswith("last ") else None
    return build_excel(
        ctx.kpis,
        same_length_prev,
        K.monthly_summary(ctx.orders),
        K.category_summary(ctx.items, ctx.orders),
        K.state_summary(ctx.orders),
        filter_description(f),
        excluded_description(ctx.meta),
        ctx.prev_label if same_length_prev is not None else "",
    )


@st.cache_data(show_spinner=False, max_entries=64)
def cached_context(f: Filters) -> Context:
    return build_context(f)


def current_context() -> Context:
    return cached_context(st.session_state["filters"])


# ---------------------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------------------
CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}
h1 {font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0 !important;}
.subtitle {color: #59636E; font-size: 1.02rem; margin: 0.15rem 0 0.4rem 0;}
.data-note {color: #59636E; font-size: 0.84rem; background: #F6F8FA; border-radius: 8px;
            padding: 0.45rem 0.8rem; margin: 0.3rem 0 1.1rem 0; border: 1px solid #EAEEF2;}
.kpi {border: 1px solid #E4E8EC; border-radius: 12px; padding: 0.95rem 1.1rem 0.85rem;
      background: #FFFFFF; height: 100%; min-height: 122px;}
.kpi .label {color: #59636E; font-size: 0.86rem; font-weight: 500; margin-bottom: 0.2rem;}
.kpi .value {color: #1F2328; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em;
             line-height: 1.2;}
.kpi .delta {font-size: 0.82rem; margin-top: 0.3rem; color: #59636E;}
.kpi .delta b {font-weight: 600;}
.section-title {font-size: 1.12rem; font-weight: 650; color: #1F2328; margin: 1.3rem 0 0.1rem;}
.section-sub {color: #59636E; font-size: 0.88rem; margin-bottom: 0.3rem;}
.insights {border-left: 4px solid #1F6FEB; background: #F3F8FF; border-radius: 10px;
           padding: 0.9rem 1.2rem; margin: 0.6rem 0 0.4rem;}
.insights h4 {margin: 0 0 0.4rem 0; font-size: 1rem; color: #0A3069;}
.insights ul {margin: 0; padding-left: 1.1rem;}
.insights li {margin: 0.25rem 0; color: #1F2328; font-size: 0.95rem;}
.explain {background: #F6F8FA; border-radius: 10px; padding: 0.9rem 1.1rem; font-size: 0.92rem;
          color: #1F2328; border: 1px solid #EAEEF2; height: 100%;}
section[data-testid="stSidebar"] .stDownloadButton button {font-weight: 600;}
</style>
"""


def page_header(title: str, subtitle: str, ctx: Context) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)
    note = excluded_description(ctx.meta)
    if ctx.filters.states or ctx.filters.categories:
        note += " Filters active: " + filter_description(ctx.filters).split(" · ", 1)[1] + "."
    st.markdown(f'<div class="data-note">ⓘ {escape(note)}</div>', unsafe_allow_html=True)


def section(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{escape(subtitle)}</div>', unsafe_allow_html=True)


def _delta_html(
    cur: float, prev: float | None, kind: str, higher_is_better: bool, prev_label: str
) -> str:
    if prev is None or prev_label == "":
        return '<div class="delta">No earlier period to compare with</div>'
    if kind == "pts":  # rates: difference in percentage points
        diff = (cur - prev) * 100
        text = f"{diff:+.1f} pts"
    elif kind == "abs":  # scores, days
        diff = cur - prev
        text = f"{diff:+.2f}"
    else:
        diff = K.relative_change(cur, prev)
        text = fmt_pct(diff, signed=True)
    if diff is None or not np.isfinite(diff):
        return '<div class="delta">No comparison available</div>'
    good = (diff >= 0) == higher_is_better
    color = ACCENT if good else RED
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "■")
    label = prev_label if prev_label.startswith("last ") else f"vs {prev_label}"
    return f'<div class="delta"><b style="color:{color}">{arrow} {text}</b> {escape(label)}</div>'


KPI_SPECS: dict[str, tuple[str, callable, str, bool]] = {
    # key: (label, formatter, delta kind, higher is better)
    "revenue": ("Revenue", fmt_money, "pct", True),
    "orders": ("Orders", fmt_int, "pct", True),
    "aov": ("Average order value", fmt_money_exact, "pct", True),
    "customers": ("Customers", fmt_int, "pct", True),
    "on_time_rate": ("On-time delivery", fmt_pct, "pts", True),
    "repeat_rate": ("Repeat customers", lambda v: fmt_pct(v, 1), "pts", True),
    "avg_delivery_days": ("Average delivery time", fmt_days, "abs", False),
    "avg_review": ("Average review", fmt_score, "abs", True),
    "late_review_gap": (
        "Review drop when late",
        lambda v: f"{v:.2f} pts" if np.isfinite(v) else "—",
        "abs",
        False,
    ),
    "freight_share": ("Shipping share of spend", fmt_pct, "pts", False),
}


def kpi_cards(ctx: Context, keys: list[str], cols: list | None = None) -> None:
    cols = cols if cols is not None else st.columns(len(keys))
    shown = ctx.kpis.as_dict()
    cur = (ctx.cmp_kpis or ctx.kpis).as_dict()
    prev = ctx.prev_kpis.as_dict() if ctx.prev_kpis else {}
    for col, key in zip(cols, keys, strict=True):
        label, fmt, kind, hib = KPI_SPECS[key]
        delta = _delta_html(cur[key], prev.get(key), kind, hib, ctx.prev_label)
        col.markdown(
            f'<div class="kpi"><div class="label">{label}</div>'
            f'<div class="value">{fmt(shown[key])}</div>{delta}</div>',
            unsafe_allow_html=True,
        )


def custom_card(col, label: str, value: str, note: str = "") -> None:
    col.markdown(
        f'<div class="kpi"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(value)}</div><div class="delta">{note}</div></div>',
        unsafe_allow_html=True,
    )


def insights_box(lines: list[str], title: str = "Key insights") -> None:
    items = "".join(f"<li>{line}</li>" for line in lines if line)
    st.markdown(
        f'<div class="insights"><h4>💡 {escape(title)}</h4><ul>{items}</ul></div>',
        unsafe_allow_html=True,
    )


def empty_selection_guard(ctx: Context) -> None:
    if ctx.kpis.orders == 0:
        st.warning("No delivered orders match these filters. Widen the period or clear a filter.")
        st.stop()


PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "displayModeBar": False,
}


def chart(fig) -> None:
    st.plotly_chart(fig, config=PLOTLY_CONFIG, width="stretch")


# ---------------------------------------------------------------------------------------
# Auto-generated insights (Overview)
# ---------------------------------------------------------------------------------------
def overview_insights(ctx: Context) -> list[str]:
    out: list[str] = []
    monthly = K.monthly_summary(ctx.orders)
    if len(monthly) >= 2:
        # With 6+ months, compare 3-month averages: one odd month cannot distort the trend.
        k = 3 if len(monthly) >= 6 else 1
        head, tail = monthly.head(k), monthly.tail(k)
        a, b = head["revenue"].mean(), tail["revenue"].mean()
        g = K.period_growth(a, b)
        verb = "grew" if g >= 0 else "fell"
        if k == 1:
            span = (
                f"between {fmt_month(head['month'].iloc[0])} ({fmt_money(a)}) and "
                f"{fmt_month(tail['month'].iloc[0])} ({fmt_money(b)})"
            )
        else:
            span = (
                f"from {fmt_money(a)} a month in "
                f"{_period_label(head['month'].iloc[0], head['month'].iloc[-1])} to "
                f"{fmt_money(b)} a month in "
                f"{_period_label(tail['month'].iloc[0], tail['month'].iloc[-1])}"
            )
        out.append(f"Monthly revenue <b>{verb} {fmt_pct(abs(g))}</b> {span}.")
        best = monthly.loc[monthly["revenue"].idxmax()]
        out.append(
            f"The best month was <b>{fmt_month(best['month'])}</b> with "
            f"{fmt_money(best['revenue'])} from {best['orders']:,.0f} orders"
            + (" — the Black Friday effect." if best["month"].month == 11 else ".")
        )
    cats = K.category_summary(ctx.items, ctx.orders)
    if len(cats) >= 2 and not ctx.filters.categories:
        top = cats.iloc[0]
        top3 = cats.head(3)["revenue_share"].sum()
        out.append(
            f"Top category <b>{escape(str(top['category']))}</b> brings "
            f"<b>{fmt_pct(top['revenue_share'])}</b> of revenue; the top 3 together bring "
            f"{fmt_pct(top3)} — revenue is spread across many categories."
        )
    gap = ctx.kpis.late_review_gap
    if np.isfinite(gap):
        out.append(
            f"Late orders score <b>{gap:.1f} points lower</b> in customer reviews "
            f"(out of 5) — on-time delivery protects ratings."
        )
    return out
