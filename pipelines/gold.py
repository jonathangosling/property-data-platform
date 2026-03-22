import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

SW_AREA_CODES = [
    "SW1", "SW2", "SW3", "SW4", "SW5", "SW6", "SW7", "SW8", "SW9",
    "SW10", "SW11", "SW12", "SW13", "SW14", "SW15", "SW16", "SW17",
    "SW18", "SW19", "SW20",
]


def _extract_area_code(postcode_col):
    """Extract area code (e.g. SW11) from a full postcode (e.g. SW11 1AA)."""
    return F.substring_index(postcode_col, " ", 1)



@dlt.table(name="gold_area_dim", comment="SW London area code reference table.")
def gold_area_dim():
    district_map = {
        "SW1": "Westminster", "SW2": "Brixton", "SW3": "Chelsea",
        "SW4": "Clapham", "SW5": "Earl's Court", "SW6": "Fulham",
        "SW7": "South Kensington", "SW8": "South Lambeth", "SW9": "Stockwell",
        "SW10": "West Brompton", "SW11": "Battersea", "SW12": "Balham",
        "SW13": "Barnes", "SW14": "Mortlake", "SW15": "Putney",
        "SW16": "Streatham", "SW17": "Tooting", "SW18": "Wandsworth",
        "SW19": "Wimbledon", "SW20": "West Wimbledon",
    }
    rows = list(district_map.items()) + [("all", "All districts")]
    return spark.createDataFrame(rows, ["area_code", "district"])


@dlt.table(
    name="gold_property_fact",
    comment="Aggregated avg/median price and property count by date and area.",
)
def gold_property_fact():
    prices = dlt.read("silver_prices")
    props = dlt.read("silver_properties")

    joined = (
        prices.join(props, "prop_id")
        .withColumn("area_code", _extract_area_code(F.col("postcode")))
        .filter(F.col("area_code").isin(SW_AREA_CODES))
    )

    area_agg = joined.groupBy("scraped_at", "area_code").agg(
        F.avg("price").cast("int").alias("avg_price"),
        F.percentile_approx("price", 0.5).cast("int").alias("median_price"),
        F.count("*").alias("num_properties"),
    ).withColumnRenamed("scraped_at", "date")

    all_agg = prices.groupBy("scraped_at").agg(
        F.avg("price").cast("int").alias("avg_price"),
        F.percentile_approx("price", 0.5).cast("int").alias("median_price"),
        F.count("*").alias("num_properties"),
    ).withColumnRenamed("scraped_at", "date").withColumn("area_code", F.lit("all"))

    return (
        area_agg.unionByName(all_agg)
        .withColumn("month", F.date_format(F.col("date"), "MMMM"))
        .withColumn("year", F.date_format(F.col("date"), "yyyy"))
    )


@dlt.table(
    name="gold_current_properties",
    comment="Snapshot of properties available on the most recent scrape date.",
)
def gold_current_properties():
    prices = dlt.read("silver_prices")
    props = dlt.read("silver_properties")

    max_date = prices.agg(F.max("scraped_at")).collect()[0][0]

    return (
        prices.filter(F.col("scraped_at") == max_date)
        .join(props, "prop_id")
        .withColumn("area_code", _extract_area_code(F.col("postcode")))
        .withColumn(
            "area_code",
            F.when(F.col("area_code").isin(SW_AREA_CODES), F.col("area_code")),
        )
        .select(
            "prop_id", "address", "postcode", "latitude", "longitude",
            "area_code", "price", "scraped_at",
        )
    )
