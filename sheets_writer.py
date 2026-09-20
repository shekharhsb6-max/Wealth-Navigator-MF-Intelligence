from __future__ import annotations

import json
import os
from typing import Iterable, List

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


SHEETS = {
    "MF_MASTER": [
        "Scheme_Code", "Scheme_Name", "Fund_House", "Scheme_Type",
        "Scheme_Category", "ISIN_Growth", "ISIN_Dividend", "Plan",
        "Option", "Active", "Updated_At"
    ],
    "MF_LATEST": [
        "Scheme_Code", "Scheme_Name", "Latest_NAV", "NAV_Date", "Updated_At"
    ],
    "MF_NAV": ["Scheme_Code", "Date", "NAV"],
    "MF_ANALYTICS": [
        "Scheme_Code", "Scheme_Name", "Latest_NAV", "NAV_Date",
        "Return_1M", "Return_3M", "Return_6M", "Return_1Y",
        "CAGR_3Y", "CAGR_5Y", "SMA20", "SMA50", "SMA200",
        "Max_Drawdown", "Trend", "Updated_At"
    ],
    "MF_WATCHLIST": ["Scheme_Code", "Scheme_Name", "Notes", "Added_At"],
    "MF_TRANSACTIONS": [
        "Date", "Owner", "Scheme_Code", "Transaction",
        "Units", "NAV", "Amount", "Folio", "Notes"
    ],
    "MF_PORTFOLIO": [
        "Owner", "Scheme_Code", "Scheme_Name", "Units",
        "Average_NAV", "Invested_Value", "Current_NAV",
        "Current_Value", "P_L", "P_L_Percent", "Updated_At"
    ],
    "MF_SETTINGS": ["Key", "Value"],
}


def client():
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set")

    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(sheet_id)


def setup():
    book = client()
    existing = {w.title: w for w in book.worksheets()}
    for name, headers in SHEETS.items():
        ws = existing.get(name)
        if ws is None:
            ws = book.add_worksheet(title=name, rows=1000, cols=max(20, len(headers)))
        if ws.row_values(1) != headers:
            ws.update("1:1", [headers])
    return book


def upsert_by_key(ws, key_col: int, key_value, row: List):
    values = ws.get_all_values()
    if values:
        for idx, existing in enumerate(values[1:], start=2):
            if len(existing) >= key_col and str(existing[key_col - 1]) == str(key_value):
                ws.update(f"A{idx}:{_col(len(row))}{idx}", [row])
                return
    ws.append_row(row, value_input_option="USER_ENTERED")


def _col(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out
