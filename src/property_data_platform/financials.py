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
    "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
    "?csv.x=yes"
    "&Datefrom={d}%2F{m}%2F{y_from}"
    "&Dateto={d_to}%2F{m_to}%2F{y_to}"
    "&SeriesCodes=IUMSOIA&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"
)


def get_interest_rates(from_date: date, to_date: date) -> list[dict]:
    """Fetch SONIA rates between from_date and to_date from Bank of England."""
    # BoE requires a prior page access to set cookies.
    session = requests.Session()
    session.get("https://www.bankofengland.co.uk/boeapps/iadb/")

    url = BOE_URL.format(
        d=from_date.strftime("%d"),
        m=from_date.strftime("%m"),
        y_from=from_date.strftime("%Y"),
        d_to=to_date.strftime("%d"),
        m_to=to_date.strftime("%m"),
        y_to=to_date.strftime("%Y"),
    )
    r = session.get(url)
    if r.status_code >= 300:
        log.warning(f"BoE API returned {r.status_code} — skipping interest rates.")
        return []

    df = pd.read_csv(pd.io.common.StringIO(r.text))
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
        latest = df.sort_index().iloc[-1]
        return {
            "date": str(latest.name.date()),
            "close": round(float(latest["Close"]), 2),
            "loaded_at": loaded_at,
        }
    except Exception as e:
        log.warning(f"Failed to fetch SPY price: {e}")
        return None
