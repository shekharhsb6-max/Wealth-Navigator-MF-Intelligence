from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional


def _parse_date(value: str):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def clean_history(api_response: dict) -> List[Dict]:
    rows = []
    for item in api_response.get("data", []):
        try:
            date_text = item.get("date")
            nav = float(item.get("nav"))
            d = _parse_date(date_text)
            if d is not None:
                rows.append({"date": d, "nav": nav})
        except (TypeError, ValueError):
            continue

    rows.sort(key=lambda x: x["date"])
    # Deduplicate dates; keep the last occurrence.
    out = {}
    for row in rows:
        out[row["date"]] = row["nav"]
    return [{"date": d, "nav": nav} for d, nav in sorted(out.items())]


def nav_on_or_before(rows: List[Dict], target_date):
    candidates = [r for r in rows if r["date"] <= target_date]
    return candidates[-1] if candidates else None


def return_from_days(rows: List[Dict], days: int) -> Optional[float]:
    if not rows:
        return None
    latest = rows[-1]
    target = latest["date"].toordinal() - days
    from datetime import date
    target_date = date.fromordinal(target)
    old = nav_on_or_before(rows, target_date)
    if not old or old["nav"] <= 0:
        return None
    return (latest["nav"] / old["nav"] - 1) * 100


def cagr(rows: List[Dict], years: float) -> Optional[float]:
    if not rows or years <= 0:
        return None
    latest = rows[-1]
    target_days = int(years * 365.25)
    from datetime import timedelta
    old = nav_on_or_before(rows, latest["date"] - timedelta(days=target_days))
    if not old or old["nav"] <= 0:
        return None
    actual_years = (latest["date"] - old["date"]).days / 365.25
    if actual_years <= 0:
        return None
    return ((latest["nav"] / old["nav"]) ** (1 / actual_years) - 1) * 100


def sma(rows: List[Dict], window: int) -> Optional[float]:
    if len(rows) < window:
        return None
    values = [r["nav"] for r in rows[-window:]]
    return sum(values) / window


def max_drawdown(rows: List[Dict]) -> Optional[float]:
    if not rows:
        return None
    peak = rows[0]["nav"]
    worst = 0.0
    for row in rows:
        peak = max(peak, row["nav"])
        if peak:
            dd = (row["nav"] / peak - 1) * 100
            worst = min(worst, dd)
    return worst


def analyze(rows: List[Dict]) -> Dict:
    if not rows:
        return {}

    latest = rows[-1]["nav"]
    s20 = sma(rows, 20)
    s50 = sma(rows, 50)
    s200 = sma(rows, 200)

    trend = "Insufficient history"
    if s200 is not None:
        if latest > s50 > s200:
            trend = "Above SMA50 & SMA200"
        elif latest < s50 < s200:
            trend = "Below SMA50 & SMA200"
        else:
            trend = "Mixed"

    return {
        "latest_nav": latest,
        "nav_date": rows[-1]["date"].isoformat(),
        "return_1m": return_from_days(rows, 30),
        "return_3m": return_from_days(rows, 90),
        "return_6m": return_from_days(rows, 182),
        "return_1y": return_from_days(rows, 365),
        "cagr_3y": cagr(rows, 3),
        "cagr_5y": cagr(rows, 5),
        "sma20": s20,
        "sma50": s50,
        "sma200": s200,
        "max_drawdown": max_drawdown(rows),
        "trend": trend,
    }


def simulate_monthly_sip(rows: List[Dict], monthly_amount: float) -> Dict:
    """Simple month-start SIP approximation using the first NAV on/after each month."""
    if not rows or monthly_amount <= 0:
        return {}

    months = []
    seen = set()
    for r in rows:
        key = (r["date"].year, r["date"].month)
        if key not in seen:
            seen.add(key)
            months.append(r)

    invested = 0.0
    units = 0.0
    for r in months:
        invested += monthly_amount
        units += monthly_amount / r["nav"]

    current_value = units * rows[-1]["nav"]
    gain = current_value - invested

    return {
        "months": len(months),
        "invested": invested,
        "units": units,
        "current_value": current_value,
        "gain": gain,
        "gain_percent": (gain / invested * 100) if invested else None,
    }
