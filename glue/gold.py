"""
Glue ETL job — gold layer.

Reads from silver Iceberg tables and overwrites gold aggregation tables.
Gold tables are fully recomputed on each run (no bookmarks needed — silver
is the authoritative, deduplicated source).
"""
import sys
import time

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ["JOB_NAME", "catalog_database"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
log = glueContext.get_logger()
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

DB = args["catalog_database"]
CATALOG = "glue_catalog"

SW_AREA_CODES = [
    "SW1", "SW2", "SW3", "SW4", "SW5", "SW6", "SW7", "SW8", "SW9",
    "SW10", "SW11", "SW12", "SW13", "SW14", "SW15", "SW16", "SW17",
    "SW18", "SW19", "SW20",
]

t0 = time.time()
prices = spark.read.format("iceberg").load(f"{CATALOG}.{DB}.silver_prices")
log.info(f"[TIMING] Read silver_prices: {prices.count()} records in {time.time() - t0:.1f}s")

t0 = time.time()
props = spark.read.format("iceberg").load(f"{CATALOG}.{DB}.silver_properties")
log.info(f"[TIMING] Read silver_properties: {props.count()} records in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# gold_area_dim
# ---------------------------------------------------------------------------

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
gold_area_dim = spark.createDataFrame(rows, ["area_code", "district"])

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.gold_area_dim (
        area_code STRING,
        district STRING
    )
    USING iceberg
""")
t0 = time.time()
gold_area_dim.writeTo(f"{CATALOG}.{DB}.gold_area_dim").overwritePartitions()
log.info(f"[TIMING] Write gold_area_dim completed in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# gold_property_fact — avg/median price by date and area
# ---------------------------------------------------------------------------

joined = (
    prices.join(props, "prop_id")
    .filter(F.col("area_code").isin(SW_AREA_CODES))
)

area_agg = joined.groupBy("date", "area_code").agg(
    F.avg("price").cast("int").alias("avg_price"),
    F.percentile_approx("price", 0.5).cast("int").alias("median_price"),
    F.count("*").alias("num_properties"),
)

all_agg = prices.groupBy("date").agg(
    F.avg("price").cast("int").alias("avg_price"),
    F.percentile_approx("price", 0.5).cast("int").alias("median_price"),
    F.count("*").alias("num_properties"),
).withColumn("area_code", F.lit("all"))

gold_property_fact = (
    area_agg.unionByName(all_agg)
    .withColumn("month", F.date_format(F.col("date"), "MMMM"))
    .withColumn("year", F.date_format(F.col("date"), "yyyy"))
)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.gold_property_fact (
        date DATE,
        area_code STRING,
        avg_price INT,
        median_price INT,
        num_properties BIGINT,
        month STRING,
        year STRING
    )
    USING iceberg
""")
t0 = time.time()
gold_property_fact.writeTo(f"{CATALOG}.{DB}.gold_property_fact").overwritePartitions()
log.info(f"[TIMING] Write gold_property_fact completed in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# gold_current_properties — snapshot of most recent scrape date
# ---------------------------------------------------------------------------

w = Window.partitionBy(F.lit(1))

gold_current = (
    prices.withColumn("max_date", F.max("date").over(w))
    .filter(F.col("date") == F.col("max_date"))
    .drop("max_date")
    .join(props, "prop_id")
    .filter(F.col("area_code").isin(SW_AREA_CODES))
    .select(
        "prop_id", "address", "postcode", "latitude", "longitude",
        "area_code", "price", "date",
    )
)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.gold_current_properties (
        prop_id INT,
        address STRING,
        postcode STRING,
        latitude FLOAT,
        longitude FLOAT,
        area_code STRING,
        price INT,
        date DATE
    )
    USING iceberg
""")
t0 = time.time()
gold_current.writeTo(f"{CATALOG}.{DB}.gold_current_properties").overwritePartitions()
log.info(f"[TIMING] Write gold_current_properties completed in {time.time() - t0:.1f}s")

job.commit()
