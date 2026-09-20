# Wealth Navigator Pro — MF Intelligence Engine

A practical mutual-fund module built around MFAPI.in and Google Sheets.

## What this build does

- Search Indian mutual-fund schemes
- Fetch latest NAV
- Fetch historical NAV
- Store a local MF master + NAV database in Google Sheets
- Calculate 1M / 3M / 6M / 1Y returns
- Calculate 3Y / 5Y CAGR when enough history exists
- Calculate SMA20 / SMA50 / SMA200
- Calculate maximum drawdown
- Maintain an MF watchlist
- Run a historical SIP simulator
- Provide an Apps Script web application that can be added to your Wealth Navigator launcher
- Provide a Python batch synchronizer for GitHub Actions

## Architecture

MFAPI.in → Python / Apps Script → Google Sheets → Apps Script UI → Wealth Navigator

MFAPI is the upstream data source. Your Sheet is the working database. The application calculates analytics locally.

## Important security rule

Never commit a Google service-account JSON file to GitHub.

For GitHub Actions, store the JSON contents as a GitHub Actions secret named:
`GOOGLE_SERVICE_ACCOUNT_JSON`

Also store:
`GOOGLE_SHEET_ID`

## 1. Google Sheet setup

1. Create a Google Sheet.
2. Open Extensions → Apps Script.
3. Upload/copy everything from `apps-script/`.
4. Run `setupMFSystem()` once and authorize it.
5. Deploy → New deployment → Web app.
6. Execute as: Me.
7. Who has access: choose the access level appropriate for your own use.
8. Open the web-app URL.

The Apps Script UI is the easiest first working version because it can use `google.script.run` without exposing Google credentials in the browser.

## 2. Python setup

Create a virtual environment and install:

    pip install -r requirements.txt

Set:
- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

Then run:

    python python/run_mf_sync.py --scheme 119551

Replace the example scheme code with a real scheme code returned by MFAPI search.

## 3. GitHub Actions

Add the two secrets described above, then enable `.github/workflows/mf_sync.yml`.

The workflow is deliberately configured for a small watchlist. Do not download every scheme's entire history every day. Cache and synchronize only schemes you actually track.

## Sheets created

- MF_MASTER
- MF_LATEST
- MF_NAV
- MF_ANALYTICS
- MF_WATCHLIST
- MF_TRANSACTIONS
- MF_PORTFOLIO
- MF_SETTINGS

## Recommended next phase

After this MVP works, connect MF_PORTFOLIO to your existing family portfolio and add:
- XIRR
- family allocation
- overlap/exposure data from a separate holdings source
- alerts
- AI query layer
- your existing ETF engine


## GitHub Actions watchlist mode

After deploying Apps Script and creating the sheets:

1. Add scheme codes to `MF_WATCHLIST`.
2. Add GitHub secrets:
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`
3. The scheduled workflow runs on weekdays and synchronizes the watchlist.
4. You can also run it manually with `mode=single` for one scheme.

This design avoids downloading every Indian mutual fund's entire history every day.
