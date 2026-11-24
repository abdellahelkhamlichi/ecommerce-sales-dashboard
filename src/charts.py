"""All Plotly figure builders. Business titles, light theme, one accent colour.

Colour rules: accent blue for the main signal, greys for context, red only for a
negative signal (late deliveries, decline, worst regions).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.labels import fmt_money, fmt_pct

ACCENT = "#1F6FEB"
ACCENT_DARK = "#0A3069"
RED = "#D1242F"
GREY_DARK = "#6E7781"
GREY = "#AFB8C1"
GREY_LIGHT = "#D0D7DE"
INK = "#1F2328"
INK_MUTED = "#59636E"
GRID = "#EEF1F4"
SEQUENTIAL = [[0.0, "#B6D3FB"], [0.5, "#4F8EF0"], [1.0, ACCENT_DARK]]

FONT = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"
GEOJSON_PATH = Path(__file__).resolve().parent.parent / "assets" / "brazil_states.geojson"


def _base(fig: go.Figure, height: int = 360, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": FONT, "size": 13, "color": INK},
        hoverlabel={
            "bgcolor": "white",
            "bordercolor": GREY_LIGHT,
            "font": {"family": FONT, "size": 13, "color": INK},
        },
        showlegend=legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"color": INK_MUTED},
            "title": None,
        },
        bargap=0.25,
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=GREY_LIGHT,
        ticks="",
        tickfont={"color": INK_MUTED},
        title=None,
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor=GRID,
        linecolor=GREY_LIGHT,
        zeroline=False,
        ticks="",
        tickfont={"color": INK_MUTED},
        title=None,
    )
    return fig


def empty_figure(message: str = "No data for this selection", height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font={"color": INK_MUTED, "size": 14},
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig, height)


def _highlight(values: pd.Series, color: str = ACCENT, base: str = GREY) -> list[str]:
    top = values.max()
    return [color if v == top else base for v in values]


def _rounded(fig: go.Figure) -> go.Figure:
    fig.update_layout(barcornerradius=4)  # rounded bar ends
    return fig


# ---------------------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------------------
def monthly_trend(monthly: pd.DataFrame) -> go.Figure:
    """Revenue (line) above orders (bars) on a shared time axis — no dual y-axis."""
    if monthly.empty:
        return empty_figure()
    growth = monthly["revenue_growth"].map(
        lambda g: fmt_pct(g, signed=True) if pd.notna(g) else "first month"
    )
    custom = list(
        zip(
            monthly["revenue"].map(fmt_money),
            growth,
            monthly["orders"].map("{:,.0f}".format),
            monthly["aov"].map("R$ {:,.0f}".format),
            strict=True,
        )
    )
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.62, 0.38],
        subplot_titles=("Revenue per month", "Orders per month"),
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["month"],
            y=monthly["revenue"],
            mode="lines+markers",
            name="Revenue",
            line={"color": ACCENT, "width": 2.5},
            marker={"size": 7, "color": ACCENT, "line": {"color": "white", "width": 2}},
            fill="tozeroy",
            fillcolor="rgba(31,111,235,0.07)",
            customdata=custom,
            hovertemplate="<b>%{x|%B %Y}</b><br>Revenue: %{customdata[0]}"
            "<br>Growth vs previous month: %{customdata[1]}"
            "<br>Orders: %{customdata[2]}<br>Average order: %{customdata[3]}"
            "<extra></extra>",
        ),
        row=1,
        col=1,
    )
    colors = [RED if (pd.notna(g) and g < -0.10) else GREY for g in monthly["revenue_growth"]]
    fig.add_trace(
        go.Bar(
            x=monthly["month"],
            y=monthly["orders"],
            name="Orders",
            marker_color=colors,
            customdata=custom,
            hovertemplate="<b>%{x|%B %Y}</b><br>Orders: %{customdata[2]}"
            "<br>Revenue growth: %{customdata[1]}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    _base(fig, height=430)
    _rounded(fig)
    fig.update_layout(margin={"l": 8, "r": 8, "t": 30, "b": 8}, hovermode="x")
    fig.update_annotations(font={"size": 13, "color": INK_MUTED}, x=0, xanchor="left")
    fig.update_yaxes(tickprefix="R$ ", tickformat="~s", row=1, col=1, rangemode="tozero")
    fig.update_yaxes(tickformat="~s", row=2, col=1)
    fig.update_xaxes(dtick="M2", tickformat="%b<br>%Y", row=2, col=1)
    return fig


def weekday_bars(df: pd.DataFrame) -> go.Figure:
    if df["revenue"].sum() == 0:
        return empty_figure()
    fig = go.Figure(
        go.Bar(
            x=[d[:3] for d in df["weekday"]],
            y=df["revenue"],
            marker_color=_highlight(df["revenue"]),
            customdata=list(
                zip(df["weekday"], df["revenue"].map(fmt_money), df["orders"], strict=True)
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>Revenue: %{customdata[1]}"
            "<br>Orders: %{customdata[2]:,}<extra></extra>",
        )
    )
    fig.update_yaxes(tickprefix="R$ ", tickformat="~s")
    return _rounded(_base(fig, 300))


def hour_bars(df: pd.DataFrame) -> go.Figure:
    if df["revenue"].sum() == 0:
        return empty_figure()
    fig = go.Figure(
        go.Bar(
            x=df["hour"],
            y=df["revenue"],
            marker_color=_highlight(df["revenue"]),
            customdata=list(zip(df["revenue"].map(fmt_money), df["orders"], strict=True)),
            hovertemplate="<b>%{x}:00 – %{x}:59</b><br>Revenue: %{customdata[0]}"
            "<br>Orders: %{customdata[1]:,}<extra></extra>",
        )
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=list(range(0, 24, 3)),
        ticktext=[f"{h}h" for h in range(0, 24, 3)],
    )
    fig.update_yaxes(tickprefix="R$ ", tickformat="~s")
    fig.update_layout(bargap=0.15)
    return _rounded(_base(fig, 300))


# ---------------------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------------------
def top_categories_bar(cats: pd.DataFrame, n: int = 15) -> go.Figure:
    if cats.empty:
        return empty_figure()
    d = cats.head(n).iloc[::-1]
    few = len(d) < 3  # a colour scale is meaningless with one or two bars
    marker = (
        {"color": ACCENT}
        if few
        else {
            "color": d["aov"],
            "colorscale": SEQUENTIAL,
            "showscale": True,
            "colorbar": {
                "title": {
                    "text": "Average<br>order",
                    "side": "top",
                    "font": {"size": 12, "color": INK_MUTED},
                },
                "tickprefix": "R$ ",
                "thickness": 10,
                "len": 0.7,
                "outlinewidth": 0,
                "tickfont": {"color": INK_MUTED},
            },
        }
    )
    fig = go.Figure(
        go.Bar(
            y=d["category"],
            x=d["revenue"],
            orientation="h",
            marker=marker,
            text=d["revenue"].map(fmt_money),
            textposition="outside",
            cliponaxis=False,
            textfont={"color": INK_MUTED, "size": 12},
            customdata=list(
                zip(
                    d["revenue"].map(fmt_money),
                    d["aov"].map("R$ {:,.0f}".format),
                    d["orders"],
                    d["revenue_share"].map(fmt_pct),
                    strict=True,
                )
            ),
            hovertemplate="<b>%{y}</b><br>Revenue: %{customdata[0]} (%{customdata[3]} of total)"
            "<br>Orders: %{customdata[2]:,}<br>Average order: %{customdata[1]}"
            "<extra></extra>",
        )
    )
    fig.update_xaxes(visible=False, range=[0, d["revenue"].max() * 1.18])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    fig.update_layout(bargap=0.3)
    return _rounded(_base(fig, max(200, min(520, 34 * len(d) + 40))))


def category_treemap(cats: pd.DataFrame, top_n: int = 20) -> go.Figure:
    if cats.empty:
        return empty_figure()
    d = cats.head(top_n).copy()
    shares = d["revenue_share"]
    lo, hi = float(shares.min()), float(shares.max())

    def shade(v: float) -> str:  # light -> dark blue by share; grey for "other"
        t = 0.0 if hi == lo else (v - lo) / (hi - lo)
        a, b = (0xB6, 0xD3, 0xFB), (0x1F, 0x6F, 0xEB)
        return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b, strict=True))

    colors = [shade(v) for v in shares]
    if len(cats) > top_n:
        rest = cats.iloc[top_n:]
        d = pd.concat(
            [
                d,
                pd.DataFrame(
                    {
                        "category": [f"{len(rest)} other categories"],
                        "revenue": [rest["revenue"].sum()],
                        "revenue_share": [rest["revenue_share"].sum()],
                        "orders": [rest["orders"].sum()],
                    }
                ),
            ]
        )
        colors.append(GREY_LIGHT)
    fig = go.Figure(
        go.Treemap(
            labels=d["category"],
            parents=[""] * len(d),
            values=d["revenue"],
            marker={"colors": colors, "line": {"color": "white", "width": 2}},
            customdata=list(
                zip(d["revenue"].map(fmt_money), d["revenue_share"].map(fmt_pct), strict=True)
            ),
            texttemplate="<b>%{label}</b><br>%{customdata[1]}",
            hovertemplate="<b>%{label}</b><br>Revenue: %{customdata[0]}<br>Share: %{customdata[1]}"
            "<extra></extra>",
            textfont={"family": FONT, "size": 13, "color": INK},
            sort=True,
            tiling={"pad": 2},
        )
    )
    fig = _base(fig, 520)
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, uniformtext={"minsize": 11, "mode": "hide"}
    )
    return fig


def category_scatter(cats: pd.DataFrame) -> go.Figure:
    if cats.empty:
        return empty_figure()
    d = cats[cats["orders"] >= 10].copy()
    if d.empty:
        return empty_figure("Not enough orders per category for this view")
    size_ref = 2.0 * d["revenue"].max() / (46**2)
    # Label only a few telling categories, each placed away from the dense cluster.
    positions: dict[str, str] = {}
    for cat, pos in [
        (d.nlargest(1, "avg_price")["category"].iloc[0], "top center"),
        (d.nlargest(1, "orders")["category"].iloc[0], "bottom center"),
        (d.nlargest(1, "revenue")["category"].iloc[0], "top left"),
        (d.nlargest(1, "aov")["category"].iloc[0] if "aov" in d else None, "middle left"),
    ]:
        if cat is not None and cat not in positions:
            positions[cat] = pos
    fig = go.Figure(
        go.Scatter(
            x=d["orders"],
            y=d["avg_price"],
            mode="markers+text",
            text=[c if c in positions else "" for c in d["category"]],
            textposition=[positions.get(c, "top center") for c in d["category"]],
            textfont={"size": 12, "color": INK},
            marker={
                "size": d["revenue"],
                "sizemode": "area",
                "sizeref": size_ref,
                "sizemin": 5,
                "color": ACCENT,
                "opacity": 0.55,
                "line": {"color": "white", "width": 2},
            },
            customdata=list(
                zip(
                    d["category"],
                    d["revenue"].map(fmt_money),
                    d["avg_price"].map("R$ {:,.0f}".format),
                    strict=True,
                )
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>Orders: %{x:,}"
            "<br>Average item price: %{customdata[2]}"
            "<br>Revenue: %{customdata[1]}<extra></extra>",
        )
    )
    fig.update_xaxes(
        type="log",
        tickvals=[10, 30, 100, 300, 1000, 3000, 10000],
        ticktext=["10", "30", "100", "300", "1,000", "3,000", "10,000"],
        title={"text": "Number of orders (log scale)", "font": {"color": INK_MUTED, "size": 12}},
        showgrid=True,
        gridcolor=GRID,
    )
    fig.update_yaxes(
        type="log",
        tickvals=[20, 50, 100, 200, 500, 1000],
        ticktext=["R$ 20", "R$ 50", "R$ 100", "R$ 200", "R$ 500", "R$ 1,000"],
        title={"text": "Average item price (log scale)", "font": {"color": INK_MUTED, "size": 12}},
    )
    return _base(fig, 460)


# ---------------------------------------------------------------------------------------
# Customers & regions
# ---------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _geojson() -> dict | None:
    if GEOJSON_PATH.exists():
        return json.loads(GEOJSON_PATH.read_text())
    return None


def _interp(stops: list[list], t: float) -> str:
    """Colour at position t (0-1) on a [[pos, hex], ...] scale."""
    t = min(max(t, 0.0), 1.0)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:], strict=False):
        if t <= p1:
            u = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            a = [int(c0[i : i + 2], 16) for i in (1, 3, 5)]
            b = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
            return "#" + "".join(f"{round(x + (y - x) * u):02X}" for x, y in zip(a, b, strict=True))
    return stops[-1][1]


def state_map(states: pd.DataFrame) -> go.Figure:
    """Choropleth drawn from the bundled GeoJSON: no map tiles, works fully offline."""
    if states.empty:
        return empty_figure()
    geo = _geojson()
    if geo is None:
        return state_bar(states)
    data = states.set_index(states["state_code"].astype(str))
    vmax = float(data["revenue"].max())
    fig = go.Figure()
    for feat in geo["features"]:
        code = feat["id"]
        polys = feat["geometry"]["coordinates"]
        if feat["geometry"]["type"] == "Polygon":
            polys = [polys]
        xs: list = []
        ys: list = []
        for poly in polys:
            ring = poly[0]
            xs += [p[0] for p in ring] + [None]
            ys += [p[1] for p in ring] + [None]
        if code in data.index:
            r = data.loc[code]
            color = _interp(SEQUENTIAL, (r["revenue"] / vmax) ** 0.5 if vmax else 0)
            hover = (
                f"<b>{r['state']}</b><br>Revenue: {fmt_money(r['revenue'])} "
                f"({fmt_pct(r['revenue_share'])})<br>Orders: {r['orders']:,.0f}"
                f"<br>Average order: R$ {r['aov']:,.0f}"
            )
        else:
            color, hover = "#F0F2F4", f"<b>{feat['properties']['name']}</b><br>No orders"
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                fill="toself",
                fillcolor=color,
                line={"color": "white", "width": 1},
                hoveron="fills",
                text=hover,
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )
        )
    # Label the five largest markets on the map.
    for code in data.head(5).index:
        feat = next((f for f in geo["features"] if f["id"] == code), None)
        if feat is None:
            continue
        polys = feat["geometry"]["coordinates"]
        ring = max(
            (p[0] for p in ([polys] if feat["geometry"]["type"] == "Polygon" else polys)), key=len
        )
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        fig.add_annotation(
            x=cx, y=cy, text=f"<b>{code}</b>", showarrow=False, font={"size": 11, "color": "white"}
        )
    # Colour legend (sqrt scale keeps smaller states distinguishable).
    ticks = [v for v in (100_000, 500_000, 1_000_000, 2_000_000, 5_000_000) if v <= vmax]
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            showlegend=False,
            hoverinfo="skip",
            marker={
                "colorscale": SEQUENTIAL,
                "cmin": 0,
                "cmax": 1,
                "color": [0],
                "colorbar": {
                    "title": {"text": "Revenue", "font": {"size": 12, "color": INK_MUTED}},
                    "tickvals": [(v / vmax) ** 0.5 for v in ticks],
                    "ticktext": [fmt_money(v, 0) for v in ticks],
                    "thickness": 10,
                    "len": 0.6,
                    "outlinewidth": 0,
                    "tickfont": {"color": INK_MUTED},
                },
            },
        )
    )
    fig = _base(fig, 500)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(margin={"l": 0, "r": 0, "t": 0, "b": 0}, hovermode="closest")
    return fig


def state_bar(states: pd.DataFrame, n: int = 15) -> go.Figure:
    d = states.head(n).iloc[::-1]
    fig = go.Figure(
        go.Bar(
            y=d["state"],
            x=d["revenue"],
            orientation="h",
            marker_color=ACCENT,
            text=d["revenue"].map(fmt_money),
            textposition="outside",
            cliponaxis=False,
            textfont={"color": INK_MUTED},
            hovertemplate="<b>%{y}</b><br>Revenue: %{text}<extra></extra>",
        )
    )
    fig.update_xaxes(visible=False, range=[0, d["revenue"].max() * 1.18])
    return _rounded(_base(fig, 480))


def top_cities_bar(cities: pd.DataFrame) -> go.Figure:
    if cities.empty:
        return empty_figure()
    d = cities.iloc[::-1]
    colors = [GREY] * (len(d) - 1) + [ACCENT]
    fig = go.Figure(
        go.Bar(
            y=d["label"],
            x=d["revenue"],
            orientation="h",
            marker_color=colors,
            text=d["revenue"].map(fmt_money),
            textposition="outside",
            cliponaxis=False,
            textfont={"color": INK_MUTED, "size": 12},
            customdata=d["orders"],
            hovertemplate="<b>%{y}</b><br>Revenue: %{text}<br>Orders: %{customdata:,}"
            "<extra></extra>",
        )
    )
    fig.update_xaxes(visible=False, range=[0, d["revenue"].max() * 1.2])
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    return _rounded(_base(fig, 420))


def new_vs_returning_bar(nr: pd.DataFrame) -> go.Figure:
    if nr.empty:
        return empty_figure()
    total = nr["New customers"] + nr["Returning customers"]
    share = (nr["Returning customers"] / total).map(fmt_pct)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=nr["month"],
            y=nr["New customers"],
            name="New customers",
            marker={"color": ACCENT, "line": {"color": "white", "width": 1}},
            hovertemplate="<b>%{x|%B %Y}</b><br>New customers: %{y:,}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=nr["month"],
            y=nr["Returning customers"],
            name="Returning customers",
            marker={"color": GREY_DARK, "line": {"color": "white", "width": 1}},
            customdata=share,
            hovertemplate="<b>%{x|%B %Y}</b><br>Returning customers: %{y:,}"
            " (%{customdata} of buyers)<extra></extra>",
        )
    )
    fig = _base(fig, 380, legend=True)
    fig.update_layout(barmode="stack", legend_traceorder="normal")
    fig.update_xaxes(dtick="M2", tickformat="%b<br>%Y")
    fig.update_yaxes(tickformat="~s")
    return fig


# ---------------------------------------------------------------------------------------
# Delivery & satisfaction
# ---------------------------------------------------------------------------------------
def delivery_histogram(orders: pd.DataFrame, cap: int = 60) -> go.Figure:
    days = orders["delivery_days"].dropna()
    if days.empty:
        return empty_figure()
    clipped = days.clip(upper=cap).round().astype(int)
    counts = clipped.value_counts().reindex(range(0, cap + 1), fill_value=0)
    median = float(days.median())
    colors = [RED if d >= 30 else GREY for d in counts.index]
    labels = [f"{d}+ days" if d == cap else f"{d} days" for d in counts.index]
    fig = go.Figure(
        go.Bar(
            x=counts.index,
            y=counts.to_numpy(),
            marker_color=colors,
            customdata=labels,
            hovertemplate="<b>%{customdata}</b><br>Orders: %{y:,}<extra></extra>",
        )
    )
    fig.add_vline(x=median, line={"color": ACCENT, "width": 2, "dash": "dot"})
    fig.add_annotation(
        x=median,
        y=1,
        yref="paper",
        text=f"Typical order: {median:.0f} days",
        showarrow=False,
        xanchor="left",
        xshift=6,
        font={"color": ACCENT, "size": 12},
    )
    fig.update_xaxes(
        title={"text": "Days from purchase to delivery", "font": {"color": INK_MUTED, "size": 12}}
    )
    fig.update_yaxes(tickformat="~s")
    fig.update_layout(bargap=0.1)
    return _base(fig, 340)


def on_time_by_state_bar(states: pd.DataFrame, overall: float, min_orders: int = 100) -> go.Figure:
    d = states[states["orders"] >= min_orders].sort_values("on_time_rate")
    if d.empty:
        return empty_figure("Not enough orders per state for this view")
    worst = set(d.head(5)["state_code"]) if len(d) > 6 else set()
    colors = [RED if s in worst else GREY for s in d["state_code"]]
    fig = go.Figure(
        go.Bar(
            x=d["state_code"].astype(str),
            y=d["on_time_rate"],
            marker_color=colors,
            customdata=list(
                zip(
                    d["state"],
                    d["on_time_rate"].map(fmt_pct),
                    d["orders"],
                    d["avg_delivery_days"].map("{:.1f} days".format),
                    strict=True,
                )
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>On time: %{customdata[1]}"
            "<br>Average delivery: %{customdata[3]}"
            "<br>Orders: %{customdata[2]:,}<extra></extra>",
        )
    )
    fig.add_hline(y=overall, line={"color": ACCENT, "width": 2, "dash": "dot"})
    fig.add_annotation(
        x=0,
        xref="paper",
        y=overall,
        text=f"Average {fmt_pct(overall)}",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        yshift=2,
        font={"color": ACCENT, "size": 12},
    )
    lo = max(0.0, float(d["on_time_rate"].min()) - 0.05)
    fig.update_yaxes(tickformat=".0%", range=[lo, 1.0])
    return _rounded(_base(fig, 360))


def review_on_time_vs_late(df: pd.DataFrame) -> go.Figure:
    if df["orders"].fillna(0).sum() == 0:
        return empty_figure()
    fig = go.Figure(
        go.Bar(
            x=df["delivery"],
            y=df["avg_review"],
            marker_color=[ACCENT, RED],
            text=df["avg_review"].map(lambda v: f"{v:.2f} ★" if pd.notna(v) else ""),
            textposition="outside",
            textfont={"size": 16, "color": INK},
            customdata=df["orders"],
            hovertemplate="<b>%{x}</b><br>Average review: %{y:.2f} / 5"
            "<br>Orders reviewed: %{customdata:,}<extra></extra>",
            width=0.5,
        )
    )
    fig.update_yaxes(range=[0, 5.6], tickvals=[1, 2, 3, 4, 5])
    return _rounded(_base(fig, 340))


def review_by_delay(df: pd.DataFrame) -> go.Figure:
    d = df[df["orders"] > 0]
    if d.empty:
        return empty_figure()
    colors = [ACCENT if "early" in str(b) else RED for b in d["bucket"]]
    fig = go.Figure(
        go.Bar(
            x=d["bucket"].astype(str),
            y=d["avg_review"],
            marker_color=colors,
            text=d["avg_review"].map("{:.1f}".format),
            textposition="outside",
            textfont={"color": INK_MUTED},
            customdata=d["orders"],
            hovertemplate="<b>%{x}</b><br>Average review: %{y:.2f} / 5"
            "<br>Orders: %{customdata:,}<extra></extra>",
        )
    )
    fig.update_yaxes(range=[0, 5.6], tickvals=[1, 2, 3, 4, 5])
    return _rounded(_base(fig, 340))


def monthly_on_time_line(monthly: pd.DataFrame) -> go.Figure:
    if monthly.empty:
        return empty_figure()
    d = monthly.dropna(subset=["on_time_rate"])
    fig = go.Figure(
        go.Scatter(
            x=d["month"],
            y=d["on_time_rate"],
            mode="lines+markers",
            line={"color": ACCENT, "width": 2.5},
            marker={
                "size": 8,
                "color": [RED if v < 0.85 else ACCENT for v in d["on_time_rate"]],
                "line": {"color": "white", "width": 2},
            },
            customdata=d["on_time_rate"].map(fmt_pct),
            hovertemplate="<b>%{x|%B %Y}</b><br>On time: %{customdata}<extra></extra>",
        )
    )
    fig.update_yaxes(tickformat=".0%", range=[max(0, float(d["on_time_rate"].min()) - 0.05), 1.0])
    fig.update_xaxes(dtick="M2", tickformat="%b<br>%Y")
    return _base(fig, 340)
