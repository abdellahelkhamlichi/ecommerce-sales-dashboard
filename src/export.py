"""One-click Excel summary: KPIs, Monthly, Categories, States."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.kpis import KpiSet

HEADER_FILL = PatternFill("solid", fgColor="1F6FEB")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F2328")
MUTED_FONT = Font(italic=True, size=10, color="59636E")
BAND_FILL = PatternFill("solid", fgColor="F6F8FA")
THIN = Side(style="thin", color="D0D7DE")

MONEY = '"R$" #,##0'
MONEY_2 = '"R$" #,##0.00'
INT = "#,##0"
PCT = "0.0%"
DAYS = '0.0" days"'
SCORE = "0.00"
MONTH = "mmm yyyy"


def _write_table(
    ws: Worksheet, df: pd.DataFrame, formats: dict[str, str], start_row: int = 1
) -> None:
    for c, name in enumerate(df.columns, start=1):
        cell = ws.cell(row=start_row, column=c, value=name)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r, row in enumerate(df.itertuples(index=False), start=start_row + 1):
        for c, (name, value) in enumerate(zip(df.columns, row, strict=True), start=1):
            if isinstance(value, float) and pd.isna(value):
                value = None
            elif isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
            cell = ws.cell(row=r, column=c, value=value)
            cell.number_format = formats.get(name, "General")
            cell.border = Border(bottom=THIN)
            if (r - start_row) % 2 == 0:
                cell.fill = BAND_FILL
    for c, name in enumerate(df.columns, start=1):
        width = max(len(str(name)), *(len(str(v)) for v in df.iloc[:, c - 1].head(200))) + 3
        ws.column_dimensions[get_column_letter(c)].width = min(max(width, 12), 42)
    ws.row_dimensions[start_row].height = 30
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(df.columns))}{start_row + len(df)}"


def build_excel(
    kpis: KpiSet,
    previous: KpiSet | None,
    monthly: pd.DataFrame,
    categories: pd.DataFrame,
    states: pd.DataFrame,
    filter_text: str,
    excluded_text: str,
    previous_label: str = "",
) -> bytes:
    wb = Workbook()

    # ---- KPIs ----------------------------------------------------------------------------
    ws = wb.active
    ws.title = "KPIs"
    ws["A1"] = "Sales Performance Summary"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = filter_text
    ws["A2"].font = MUTED_FONT
    ws["A3"] = excluded_text
    ws["A3"].font = MUTED_FONT

    rows = [
        ("Revenue", "revenue", MONEY),
        ("Orders", "orders", INT),
        ("Average order value", "aov", MONEY_2),
        ("Customers", "customers", INT),
        ("Repeat customer rate", "repeat_rate", PCT),
        ("On-time delivery rate", "on_time_rate", PCT),
        ("Average delivery time", "avg_delivery_days", DAYS),
        ("Average review score (1–5)", "avg_review", SCORE),
        ("Review gap: on-time vs late orders", "late_review_gap", SCORE),
        ("Shipping cost share", "freight_share", PCT),
    ]
    cur, prev = kpis.as_dict(), previous.as_dict() if previous else {}
    table = pd.DataFrame(
        {
            "Indicator": [r[0] for r in rows],
            "Selected period": [cur[r[1]] for r in rows],
            (
                f"Previous period ({previous_label})"
                if previous and previous_label
                else "Previous period"
            ): [prev.get(r[1]) for r in rows],
        }
    )
    _write_table(ws, table, {}, start_row=5)
    for i, (_, _, fmt) in enumerate(rows, start=6):
        ws.cell(row=i, column=2).number_format = fmt
        ws.cell(row=i, column=3).number_format = fmt
        cur_ref, prev_ref = f"B{i}", f"C{i}"
        ws.cell(
            row=i,
            column=4,
            value=f'=IF(OR({prev_ref}="",{prev_ref}=0),"",({cur_ref}-{prev_ref})/ABS({prev_ref}))',
        )
        ws.cell(row=i, column=4).number_format = "+0.0%;-0.0%;0.0%"
        ws.cell(row=i, column=4).border = Border(bottom=THIN)
    head = ws.cell(row=5, column=4, value="Change")
    head.fill, head.font = HEADER_FILL, HEADER_FONT
    head.alignment = Alignment(horizontal="center", vertical="center")
    ws.column_dimensions["A"].width = 38
    for col in "BCD":
        ws.column_dimensions[col].width = 18

    # ---- Monthly -------------------------------------------------------------------------
    m = monthly.rename(
        columns={
            "month": "Month",
            "revenue": "Revenue",
            "orders": "Orders",
            "customers": "Customers",
            "aov": "Average order value",
            "revenue_growth": "Revenue growth vs previous month",
            "on_time_rate": "On-time delivery rate",
            "avg_review": "Average review",
        }
    )[
        [
            "Month",
            "Revenue",
            "Orders",
            "Customers",
            "Average order value",
            "Revenue growth vs previous month",
            "On-time delivery rate",
            "Average review",
        ]
    ]
    _write_table(
        wb.create_sheet("Monthly"),
        m,
        {
            "Month": MONTH,
            "Revenue": MONEY,
            "Orders": INT,
            "Customers": INT,
            "Average order value": MONEY_2,
            "Revenue growth vs previous month": "+0.0%;-0.0%;0.0%",
            "On-time delivery rate": PCT,
            "Average review": SCORE,
        },
    )

    # ---- Categories ----------------------------------------------------------------------
    c = categories.rename(
        columns={
            "category": "Category",
            "revenue": "Revenue",
            "revenue_share": "Share of revenue",
            "orders": "Orders",
            "aov": "Average order value",
            "avg_price": "Average item price",
            "freight_share": "Shipping cost share",
            "avg_review": "Average review",
        }
    )[
        [
            "Category",
            "Revenue",
            "Share of revenue",
            "Orders",
            "Average order value",
            "Average item price",
            "Shipping cost share",
            "Average review",
        ]
    ]
    _write_table(
        wb.create_sheet("Categories"),
        c,
        {
            "Revenue": MONEY,
            "Share of revenue": PCT,
            "Orders": INT,
            "Average order value": MONEY_2,
            "Average item price": MONEY_2,
            "Shipping cost share": PCT,
            "Average review": SCORE,
        },
    )

    # ---- States --------------------------------------------------------------------------
    s = states.rename(
        columns={
            "state": "State",
            "state_code": "Code",
            "revenue": "Revenue",
            "revenue_share": "Share of revenue",
            "orders": "Orders",
            "customers": "Customers",
            "aov": "Average order value",
            "on_time_rate": "On-time delivery rate",
            "avg_delivery_days": "Average delivery time",
            "avg_review": "Average review",
        }
    )[
        [
            "State",
            "Code",
            "Revenue",
            "Share of revenue",
            "Orders",
            "Customers",
            "Average order value",
            "On-time delivery rate",
            "Average delivery time",
            "Average review",
        ]
    ]
    s["Code"] = s["Code"].astype(str)
    _write_table(
        wb.create_sheet("States"),
        s,
        {
            "Revenue": MONEY,
            "Share of revenue": PCT,
            "Orders": INT,
            "Customers": INT,
            "Average order value": MONEY_2,
            "On-time delivery rate": PCT,
            "Average delivery time": DAYS,
            "Average review": SCORE,
        },
    )

    for sheet in wb.worksheets:  # print-ready: landscape, one page wide
        sheet.page_setup.orientation = "landscape"
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
