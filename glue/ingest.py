"""
Glue Python Shell job — ingest entry point.

Orchestrates the full ingest run:
  1. Scrape Rightmove + reverse geocode (scrape.py)
  2. Fetch SPY price (financials.py)
  3. Write Parquet to S3 landing zone with year=/month=/day= partitioning

Expects scrape.py and financials.py to be co-deployed via --extra-py-files.
Supports --dry-run for local testing (skips S3 writes, falls back to env var for API key).
"""
import argparse
import logging
import os
import sys
from datetime import date
from typing import Optional

from scrape import add_postcodes, scrape_rightmove

log = logging.getLogger()
log.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(levelname)s — %(message)s"))
log.addHandler(_handler)


def _get_api_key(secret_name: str) -> Optional[str]:
    try:
        import boto3
        client = boto3.client("secretsmanager")
        return client.get_secret_value(SecretId=secret_name)["SecretString"]
    except Exception:
        pass
    return os.environ.get("GOOGLEMAPS_API_KEY")


def _write_parquet(records: list[dict], s3_path: str, today: date) -> None:
    """Write records as a single Parquet file into a Hive-partitioned S3 prefix."""
    if not records:
        log.warning(f"No records to write for {s3_path} — skipping.")
        return

    partition = f"year={today.year}/month={today.month:02d}/day={today.day:02d}"
    full_path = f"{s3_path}/{partition}/part-0.parquet"

    import pandas as pd
    pd.DataFrame(records).to_parquet(full_path, index=False)
    log.info(f"Wrote {len(records)} records to {full_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--landing_path", required=True)
    parser.add_argument("--secret_name", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Skip S3 writes — for local testing")
    args, _ = parser.parse_known_args()

    landing_path = args.landing_path.rstrip("/")
    today = date.today()

    # --- Rightmove scrape ---
    properties, prices = scrape_rightmove()

    # --- Reverse geocode ---
    api_key = _get_api_key(args.secret_name)
    if api_key:
        properties = add_postcodes(properties, api_key)
    else:
        log.warning("No Google Maps API key — postcodes not added.")
        for p in properties:
            p["postcode"] = None

    if args.dry_run:
        log.info(f"[dry-run] {len(properties)} properties, {len(prices)} prices")
        log.info(f"[dry-run] Sample property: {properties[0]}")
        log.info(f"[dry-run] Sample price:    {prices[0]}")
        return

    # --- Write to S3 landing zone ---
    _write_parquet(properties, f"{landing_path}/properties", today)
    _write_parquet(prices, f"{landing_path}/prices", today)


if __name__ == "__main__":
    main()
