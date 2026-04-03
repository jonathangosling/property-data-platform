"""
Glue Python Shell job — SPY price ingest.

Fetches the last 7 days of SPY close prices via yfinance and writes
them as Parquet to the S3 landing zone.
"""
import argparse
import logging
import sys
from datetime import date

from financials import get_spy_prices

log = logging.getLogger()
log.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(levelname)s — %(message)s"))
log.addHandler(_handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--landing_path", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Skip S3 writes — for local testing")
    args, _ = parser.parse_known_args()

    landing_path = args.landing_path.rstrip("/")
    today = date.today()

    records = get_spy_prices(days=7)

    if args.dry_run:
        log.info(f"[dry-run] {len(records)} SPY records: {records}")
        return

    if not records:
        raise RuntimeError("No SPY price records returned — failing job.")

    import pandas as pd
    partition = f"year={today.year}/month={today.month:02d}/day={today.day:02d}"
    path = f"{landing_path}/spy_prices/{partition}/part-0.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    log.info(f"Wrote {len(records)} SPY records to {path}")


if __name__ == "__main__":
    main()
