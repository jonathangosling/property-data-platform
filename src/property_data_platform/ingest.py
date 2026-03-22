"""
Databricks job entry point.

Orchestrates the full ingest run:
  1. Scrape Rightmove + reverse geocode (scrape.py)
  2. Fetch financial data (financials.py)
  3. Write all datasets to Delta landing tables on S3
"""
import argparse
import logging
import os
from datetime import date, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    FloatType, IntegerType, StringType, StructField, StructType,
)

from property_data_platform.scrape import add_postcodes, scrape_rightmove
from property_data_platform.financials import get_interest_rates, get_spy_price

log = logging.getLogger(__name__)

PROPERTIES_SCHEMA = StructType([
    StructField("prop_id", IntegerType(), False),
    StructField("address", StringType(), True),
    StructField("latitude", FloatType(), True),
    StructField("longitude", FloatType(), True),
    StructField("postcode", StringType(), True),
    StructField("scraped_at", StringType(), False),
])
PRICES_SCHEMA = StructType([
    StructField("prop_id", IntegerType(), False),
    StructField("price", IntegerType(), False),
    StructField("scraped_at", StringType(), False),
])
INTEREST_RATES_SCHEMA = StructType([
    StructField("date", StringType(), False),
    StructField("rate", FloatType(), False),
    StructField("loaded_at", StringType(), False),
])
SPY_SCHEMA = StructType([
    StructField("date", StringType(), False),
    StructField("close", FloatType(), False),
    StructField("loaded_at", StringType(), False),
])


def _get_api_key() -> str | None:
    """
    Resolve the Google Maps API key.
    On Databricks: reads from the secret scope.
    Locally: falls back to the GOOGLEMAPS_API_KEY environment variable.
    Returns None if neither is available (geocoding will be skipped).
    """
    try:
        from pyspark.dbutils import DBUtils  # noqa: PLC0415
        dbutils = DBUtils(SparkSession.getActiveSession())
        return dbutils.secrets.get("property-data-platform", "GOOGLEMAPS_API_KEY")
    except Exception:
        pass
    return os.environ.get("GOOGLEMAPS_API_KEY")


def _write_delta(
    records: list[dict],
    schema: StructType,
    path: str,
    partition_by: str | None = None,
) -> None:
    """Append records to a Delta table at the given S3 path."""
    spark = SparkSession.getActiveSession()
    writer = spark.createDataFrame(records, schema=schema).write.format("delta").mode("append")
    if partition_by:
        writer = writer.partitionBy(partition_by)
    writer.save(path)
    log.info(f"Wrote {len(records)} records to {path}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-bucket", required=True, help="S3 bucket for landing Delta tables")
    parser.add_argument("--dry-run", action="store_true", help="Skip Delta writes — for local testing")
    args = parser.parse_args()
    base = f"s3://{args.s3_bucket}/landing"

    # --- Rightmove scrape ---
    properties, prices = scrape_rightmove()

    # --- Reverse geocode ---
    api_key = _get_api_key()
    if api_key:
        properties = add_postcodes(properties, api_key)
    else:
        log.warning("No Google Maps API key available — postcodes not added.")
        for p in properties:
            p["postcode"] = None

    # --- Financial data ---
    to_date = date.today()
    from_date = to_date - timedelta(days=7)
    interest_rates = get_interest_rates(from_date, to_date)
    spy = get_spy_price()

    if args.dry_run:
        log.info(f"[dry-run] {len(properties)} properties, {len(prices)} prices, "
                 f"{len(interest_rates)} interest rates, spy={spy}")
        log.info(f"[dry-run] Sample property: {properties[0]}")
        log.info(f"[dry-run] Sample price:    {prices[0]}")
        return

    # --- Write to Delta landing tables ---
    _write_delta(properties, PROPERTIES_SCHEMA, f"{base}/properties", partition_by="scraped_at")
    _write_delta(prices, PRICES_SCHEMA, f"{base}/prices")
    if interest_rates:
        _write_delta(interest_rates, INTEREST_RATES_SCHEMA, f"{base}/interest_rates")
    if spy:
        _write_delta([spy], SPY_SCHEMA, f"{base}/spy_prices")


if __name__ == "__main__":
    main()
