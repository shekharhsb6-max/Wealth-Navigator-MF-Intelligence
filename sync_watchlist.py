from __future__ import annotations

from datetime import datetime, timezone

from mf_api import MFAPIClient
from mf_analytics import analyze, clean_history
from sheets_writer import setup, upsert_by_key


def main():
    book = setup()
    watch = book.worksheet("MF_WATCHLIST").get_all_values()
    codes = []
    for row in watch[1:]:
        if row and row[0].strip():
            codes.append(row[0].strip())

    if not codes:
        print("MF_WATCHLIST is empty. Nothing to sync.")
        return

    api = MFAPIClient()
    now = datetime.now(timezone.utc).isoformat()

    master = book.worksheet("MF_MASTER")
    latest_ws = book.worksheet("MF_LATEST")
    analytics_ws = book.worksheet("MF_ANALYTICS")
    nav_ws = book.worksheet("MF_NAV")

    existing_nav = {
        (r[0], r[1])
        for r in nav_ws.get_all_values()[1:]
        if len(r) >= 2
    }

    for code in codes:
        print(f"Syncing {code}...")
        data = api.history(code)
        rows = clean_history(data)
        if not rows:
            print(f"  No history returned for {code}")
            continue

        meta = data.get("meta", {})
        name = meta.get("scheme_name", "")
        master_row = [
            code, name, meta.get("fund_house", ""),
            meta.get("scheme_type", ""), meta.get("scheme_category", ""),
            meta.get("isin_growth", ""), meta.get("isin_dividend", ""),
            "", "", "TRUE", now
        ]
        upsert_by_key(master, 1, code, master_row)

        latest = rows[-1]
        upsert_by_key(
            latest_ws, 1, code,
            [code, name, latest["nav"], latest["date"].isoformat(), now],
        )

        new_rows = []
        for r in rows:
            key = (code, r["date"].isoformat())
            if key not in existing_nav:
                new_rows.append([code, r["date"].isoformat(), r["nav"]])
                existing_nav.add(key)
        if new_rows:
            nav_ws.append_rows(new_rows, value_input_option="USER_ENTERED")

        m = analyze(rows)
        upsert_by_key(
            analytics_ws, 1, code,
            [
                code, name, m.get("latest_nav"), m.get("nav_date"),
                m.get("return_1m"), m.get("return_3m"),
                m.get("return_6m"), m.get("return_1y"),
                m.get("cagr_3y"), m.get("cagr_5y"),
                m.get("sma20"), m.get("sma50"), m.get("sma200"),
                m.get("max_drawdown"), m.get("trend"), now,
            ],
        )

    print(f"Completed {len(codes)} scheme(s).")


if __name__ == "__main__":
    main()
