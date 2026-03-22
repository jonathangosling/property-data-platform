"""
Fetch financial indicator data:
  - Bank of England SONIA interest rates
  - SPY ETF close price (S&P 500 proxy) via yfinance
"""
import logging
from datetime import date

import pandas as pd
import requests
import yfinance as yf

log = logging.getLogger(__name__)

BOE_URL = (
    "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
    "?DAT=RNG"
    "&FD={fd}&FM={fm}&FY={fy}"
    "&TD={td}&TM={tm}&TY={ty}"
    "&SeriesCodes=IUDSOIA&CSVF=TT&UsingCodes=Y&VPD=Y&VFD=N"
)


def get_interest_rates(from_date: date, to_date: date) -> list[dict]:
    """Fetch SONIA rates between from_date and to_date from Bank of England.

    The BoE database page renders data in an HTML DataTable — the CSV button
    is client-side only, so we parse the HTML table directly with pd.read_html.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    url = BOE_URL.format(
        fd=from_date.strftime("%d"),
        fm=from_date.strftime("%b"),
        fy=from_date.strftime("%Y"),
        td=to_date.strftime("%d"),
        tm=to_date.strftime("%b"),
        ty=to_date.strftime("%Y"),
    )
    r = requests.get(url, headers=headers)
    if r.status_code >= 300:
        log.warning(f"BoE request returned {r.status_code} — skipping interest rates.")
        return []

    tables = pd.read_html(pd.io.common.StringIO(r.text))
    if not tables:
        log.warning("No tables found in BoE response — skipping interest rates.")
        return []

    df = tables[0]
    loaded_at = str(date.today())
    records = []
    for _, row in df.iterrows():
        try:
            records.append({
                "date": str(pd.to_datetime(row.iloc[0]).date()),
                "rate": float(row.iloc[1]),
                "loaded_at": loaded_at,
            })
        except Exception:
            continue

    log.info(f"Fetched {len(records)} interest rate records.")
    return records


def get_spy_price() -> dict | None:
    """Fetch the most recent SPY ETF close price."""
    loaded_at = str(date.today())
    try:
        df = yf.download("SPY", period="5d", auto_adjust=True, progress=False)
        if df.empty:
            log.warning("yfinance returned empty data for SPY.")
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        latest = df.sort_index().iloc[-1]
        return {
            "date": str(latest.name.date()),
            "close": round(float(latest["Close"]), 2),
            "loaded_at": loaded_at,
        }
    except Exception as e:
        log.warning(f"Failed to fetch SPY price: {e}")
        return None
