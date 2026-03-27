"""
Glue Python Shell job — ingest entry point.

Orchestrates the full ingest run:
  1. Scrape Rightmove + reverse geocode (scrape.py)
  2. Fetch SPY price (financials.py)
  3. Write Parquet to S3 landing zone with year=/month=/day= partitioning

Expects scrape.py and financials.py to be co-deployed via --extra-py-files.
"""
import logging
import sys
from datetime import date

import boto3
import pandas as pd

from awsglue.utils import getResolvedOptions

from scrape import add_postcodes, scrape_rightmove
from financials import get_spy_price

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger(__name__)

args = getResolvedOptions(sys.argv, ["landing_path", "secret_name"])
LANDING_PATH = args["landing_path"].rstrip("/")
SECRET_NAME = args["secret_name"]


def _get_api_key() -> str | None:
    try:
        client = boto3.client("secretsmanager")
        return client.get_secret_value(SecretId=SECRET_NAME)["SecretString"]
    except Exception as e:
        log.warning(f"Could not retrieve API key from Secrets Manager: {e}")
        return None


def _write_parquet(records: list[dict], s3_path: str, today: date) -> None:
    """Write records as a single Parquet file into a Hive-partitioned S3 prefix."""
    if not records:
        log.warning(f"No records to write for {s3_path} — skipping.")
        return

    partition = f"year={today.year}/month={today.month:02d}/day={today.day:02d}"
    full_path = f"{s3_path}/{partition}/part-0.parquet"

    pd.DataFrame(records).to_parquet(full_path, index=False)
    log.info(f"Wrote {len(records)} records to {full_path}")


def main() -> None:
    today = date.today()

    # --- Rightmove scrape ---
    properties, prices = scrape_rightmove()

    # --- Reverse geocode ---
    api_key = _get_api_key()
    if api_key:
        properties = add_postcodes(properties, api_key)
    else:
        log.warning("No Google Maps API key — postcodes not added.")
        for p in properties:
            p["postcode"] = None

    # --- Financial data ---
    spy = get_spy_price()

    # --- Write to S3 landing zone ---
    _write_parquet(properties, f"{LANDING_PATH}/properties", today)
    _write_parquet(prices, f"{LANDING_PATH}/prices", today)
    if spy:
        _write_parquet([spy], f"{LANDING_PATH}/spy_prices", today)


if __name__ == "__main__":
    main()
