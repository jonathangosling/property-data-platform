import dlt
from pyspark.sql import functions as F

S3_BUCKET = spark.conf.get("s3_bucket")


@dlt.table(
    name="bronze_properties",
    comment="Raw property records written by the scrape job.",
    table_properties={"quality": "bronze"},
)
def bronze_properties():
    return spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/properties")


@dlt.table(
    name="bronze_prices",
    comment="Raw price records written by the scrape job.",
    table_properties={"quality": "bronze"},
)
def bronze_prices():
    return spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/prices")


@dlt.table(
    name="bronze_interest_rates",
    comment="Raw Bank of England SONIA interest rate data.",
    table_properties={"quality": "bronze"},
)
def bronze_interest_rates():
    return spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/interest_rates")


@dlt.table(
    name="bronze_spy_prices",
    comment="Raw SPY ETF close prices from yfinance.",
    table_properties={"quality": "bronze"},
)
def bronze_spy_prices():
    return spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/spy_prices")
