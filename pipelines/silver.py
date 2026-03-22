import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window
# Reads raw tables, deduplictates and sets expectations

S3_BUCKET = spark.conf.get("s3_bucket")


@dlt.table(
    name="silver_properties",
    comment="Deduplicated property dimension — one row per prop_id.",
    table_properties={"quality": "silver"},
)
@dlt.expect("postcode_present", "postcode IS NOT NULL")
@dlt.expect("valid_prop_id", "prop_id IS NOT NULL")
@dlt.expect("valid_coordinates", "latitude IS NOT NULL AND longitude IS NOT NULL")
def silver_properties():
    w = Window.partitionBy("prop_id").orderBy(F.desc("scraped_at"))
    return (
        spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/properties")
        .withColumn("row_num", F.row_number().over(w))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )


@dlt.table(
    name="silver_prices",
    comment="Deduplicated price fact — one row per prop_id per date.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_price", "price > 0")
def silver_prices():
    w = Window.partitionBy("prop_id", "scraped_at").orderBy(F.desc("scraped_at"))
    return (
        spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/prices")
        .withColumn("row_num", F.row_number().over(w))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )



@dlt.table(
    name="silver_spy_prices",
    comment="Deduplicated SPY close prices — one row per date.",
    table_properties={"quality": "silver"},
)
def silver_spy_prices():
    w = Window.partitionBy("date").orderBy(F.desc("loaded_at"))
    return (
        spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/spy_prices")
        .withColumn("row_num", F.row_number().over(w))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )
