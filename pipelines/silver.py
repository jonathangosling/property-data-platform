import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window


@dlt.table(
    name="silver_properties",
    comment="Deduplicated property dimension — one row per prop_id.",
    table_properties={"quality": "silver"},
)
@dlt.expect("valid_prop_id", "prop_id IS NOT NULL")
@dlt.expect("valid_coordinates", "latitude IS NOT NULL AND longitude IS NOT NULL")
def silver_properties():
    w = Window.partitionBy("prop_id").orderBy(F.desc("scraped_at"))
    return (
        dlt.read("bronze_properties")
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
    w = Window.partitionBy("prop_id", "date").orderBy(F.desc("scraped_at"))
    return (
        dlt.read("bronze_prices")
        .withColumn("row_num", F.row_number().over(w))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )


@dlt.table(
    name="silver_interest_rates",
    comment="Deduplicated Bank of England SONIA rates — one row per date.",
    table_properties={"quality": "silver"},
)
def silver_interest_rates():
    w = Window.partitionBy("date").orderBy(F.desc("loaded_at"))
    return (
        dlt.read("bronze_interest_rates")
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
        dlt.read("bronze_spy_prices")
        .withColumn("row_num", F.row_number().over(w))
        .filter(F.col("row_num") == 1)
        .drop("row_num")
    )
