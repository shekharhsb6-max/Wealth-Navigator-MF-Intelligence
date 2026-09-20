from __future__ import annotations

import argparse
from datetime import datetime, timezone

from mf_api import MFAPIClient
from mf_analytics import analyze, clean_history
from sheets_writer import client, setup, upsert_by_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", required=True, help="MFAPI scheme code")
    args = parser.parse_args()

    book = setup()
    api = MFAPIClient()

    history_response = api.history(args.scheme)
    rows = clean_history(history_response)

    if not rows:
        raise RuntimeError("No NAV history returned")

    meta = history_response.get("meta", {})
    name = meta.get("scheme_name", "")
    fund_house = meta.get("fund_house", "")
    scheme_type = meta.get("scheme_type", "")
    scheme_category = meta.get("scheme_category", "")
    isin_growth = meta.get("isin_growth", "")
    isin_dividend = meta.get("isin_dividend", "")

    now = datetime.now(timezone.utc).isoformat()
    master = book.worksheet("MF_MASTER")
    upsert_by_key(
        master, 1, args.scheme,
        [
            args.scheme, name, fund_house, scheme_type, scheme_category,
            isin_growth, isin_dividend, "", "", "TRUE", now
        ],
    )

    latest = rows[-1]
    latest_ws = book.worksheet("MF_LATEST")
    upsert_by_key(
        latest_ws, 1, args.scheme,
        [args.scheme, name, latest["nav"], latest["date"].isoformat(), now],
    )

    nav_ws = book.worksheet("MF_NAV")
    existing = {
        (r[0], r[1])
        for r in nav_ws.get_all_values()[1:]
        if len(r) >= 2
    }
    new_rows = []
    for r in rows:
        key = (str(args.scheme), r["date"].isoformat())
        if key not in existing:
            new_rows.append([args.scheme, r["date"].isoformat(), r["nav"]])
    if new_rows:
        nav_ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    metrics = analyze(rows)
    analytics_ws = book.worksheet("MF_ANALYTICS")
    upsert_by_key(
        analytics_ws, 1, args.scheme,
        [
            args.scheme, name,
            metrics.get("latest_nav"), metrics.get("nav_date"),
            metrics.get("return_1m"), metrics.get("return_3m"),
            metrics.get("return_6m"), metrics.get("return_1y"),
            metrics.get("cagr_3y"), metrics.get("cagr_5y"),
            metrics.get("sma20"), metrics.get("sma50"),
            metrics.get("sma200"), metrics.get("max_drawdown"),
            metrics.get("trend"), now,
        ],
    )

    print(f"Synced {args.scheme}: {name}")
    print(metrics)


if __name__ == "__main__":
    main()
