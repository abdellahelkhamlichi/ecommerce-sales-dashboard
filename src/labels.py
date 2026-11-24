"""Business-friendly labels and number formatting used across the app and the export."""

from __future__ import annotations

import math

STATE_NAMES: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Federal District", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}  # fmt: skip

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

PAYMENT_NAMES = {
    "credit_card": "Credit card",
    "boleto": "Bank slip (boleto)",
    "voucher": "Voucher",
    "debit_card": "Debit card",
    "not_defined": "Other",
}

_CATEGORY_OVERRIDES = {
    "unknown": "Unknown",
    "pc_gamer": "PC Gaming",
    "computers_accessories": "Computer Accessories",
    "telephony": "Phones",
    "fixed_telephony": "Landline Phones",
    "construction_tools_construction": "Construction Tools",
    "construction_tools_lights": "Construction Lighting",
    "construction_tools_safety": "Construction Safety",
    "costruction_tools_garden": "Garden Tools (Construction)",
    "costruction_tools_tools": "Hand Tools (Construction)",
    "home_appliances_2": "Home Appliances II",
    "home_confort": "Home Comfort",
    "home_comfort_2": "Home Comfort II",
    "fashio_female_clothing": "Women's Clothing",
    "fashion_male_clothing": "Men's Clothing",
    "fashion_childrens_clothes": "Children's Clothing",
    "art": "Art",
    "arts_and_craftmanship": "Arts & Crafts",
    "cds_dvds_musicals": "CDs, DVDs & Musicals",
    "dvds_blu_ray": "DVDs & Blu-ray",
    "la_cuisine": "Gourmet Cuisine",
    "small_appliances_home_oven_and_coffee": "Ovens & Coffee Makers",
    "furniture_mattress_and_upholstery": "Mattresses & Upholstery",
    "kitchen_dining_laundry_garden_furniture": "Kitchen, Laundry & Garden Furniture",
    "signaling_and_security": "Signage & Security",
    "tablets_printing_image": "Tablets & Printing",
    "audio": "Audio",
    "auto": "Auto Parts",
    "bed_bath_table": "Bed, Bath & Table",
    "health_beauty": "Health & Beauty",
    "watches_gifts": "Watches & Gifts",
    "sports_leisure": "Sports & Leisure",
    "furniture_decor": "Furniture & Decor",
    "cool_stuff": "Cool Stuff & Gadgets",
    "fashion_bags_accessories": "Bags & Accessories",
    "consoles_games": "Consoles & Games",
    "furniture_living_room": "Living Room Furniture",
    "furniture_bedroom": "Bedroom Furniture",
    "books_general_interest": "Books (General)",
    "books_technical": "Books (Technical)",
    "books_imported": "Books (Imported)",
    "industry_commerce_and_business": "Industry & Business",
    "agro_industry_and_commerce": "Agro-Industry",
    "market_place": "Marketplace",
    "fashion_shoes": "Shoes",
    "food_drink": "Food & Drink",
    "fashion_underwear_beach": "Underwear & Beachwear",
    "cine_photo": "Cinema & Photo",
    "fashion_sport": "Sportswear",
}

OTHER = "Other"


def category_label(raw: str) -> str:
    """'health_beauty' -> 'Health & Beauty'."""
    if raw in _CATEGORY_OVERRIDES:
        return _CATEGORY_OVERRIDES[raw]
    words = raw.replace("_and_", " & ").replace("_", " ").split()
    small = {"&", "of", "and"}
    return " ".join(w if w in small else w.capitalize() for w in words)


def state_label(code: str) -> str:
    return STATE_NAMES.get(code, code)


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def fmt_money(value: float | None, decimals: int = 1) -> str:
    """R$ 1.2M, R$ 154K, R$ 860."""
    if _is_missing(value):
        return "—"
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        return f"{sign}R$ {v / 1_000_000:.{decimals}f}M"
    if v >= 1_000:
        return f"{sign}R$ {v / 1_000:.0f}K" if v >= 10_000 else f"{sign}R$ {v / 1_000:.1f}K"
    return f"{sign}R$ {v:,.0f}"


def fmt_money_exact(value: float | None) -> str:
    """R$ 159.85 — for averages such as order value."""
    if _is_missing(value):
        return "—"
    return f"R$ {value:,.2f}"


def fmt_int(value: float | None) -> str:
    if _is_missing(value):
        return "—"
    v = abs(value)
    if v >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{value:,.0f}"


def fmt_pct(value: float | None, decimals: int = 1, signed: bool = False) -> str:
    """0.1234 -> '12.3%'."""
    if _is_missing(value):
        return "—"
    return f"{value * 100:+.{decimals}f}%" if signed else f"{value * 100:.{decimals}f}%"


def fmt_days(value: float | None) -> str:
    if _is_missing(value):
        return "—"
    return f"{value:.1f} days"


def fmt_score(value: float | None) -> str:
    if _is_missing(value):
        return "—"
    return f"{value:.2f} / 5"


def fmt_month(ts) -> str:
    return ts.strftime("%b %Y")
