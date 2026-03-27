"""
Glue ETL job — silver layer.

Reads new Parquet files from the landing zone (via Job Bookmarks),
deduplicates, and upserts into Iceberg silver tables in the Glue catalog.

Job Bookmarks track the last processed S3 file per dataset, so only new
records from each ingest run are read on each execution.
"""
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ["JOB_NAME", "landing_path", "iceberg_path", "catalog_database"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

LANDING = args["landing_path"].rstrip("/")
DB = args["catalog_database"]
CATALOG = "glue_catalog"


def _read_landing(dataset: str):
    """Read new landing Parquet files using Job Bookmarks."""
    return glueContext.create_dynamic_frame.from_options(
        connection_type="s3",
        connection_options={
            "paths": [f"{LANDING}/{dataset}/"],
            "recurse": True,
        },
        format="parquet",
        transformation_ctx=f"landing_{dataset}",
    ).toDF()


# ---------------------------------------------------------------------------
# silver_properties — one row per prop_id (latest scrape wins)
# ---------------------------------------------------------------------------

raw_properties = _read_landing("properties")

w = Window.partitionBy("prop_id").orderBy(F.desc("scraped_at"))
w_all = Window.partitionBy("prop_id")

incoming_properties = (
    raw_properties
    .withColumn("row_num", F.row_number().over(w))
    .withColumn("first_scraped_at", F.min("scraped_at").over(w_all))
    .filter(F.col("row_num") == 1)
    .drop("row_num")
    .withColumn("scraped_at", F.col("scraped_at").cast("date"))
    .withColumn("first_scraped_at", F.col("first_scraped_at").cast("date"))
    .withColumn("area_code", F.substring_index(F.col("postcode"), " ", 1))
)

spark.sql(f"CREATE DATABASE IF NOT EXISTS {CATALOG}.{DB}")
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.silver_properties (
        prop_id INT,
        address STRING,
        latitude FLOAT,
        longitude FLOAT,
        postcode STRING,
        scraped_at DATE,
        first_scraped_at DATE,
        area_code STRING
    )
    USING iceberg
    TBLPROPERTIES ('format-version' = '2', 'write.target-file-size-bytes' = '134217728')
""")

incoming_properties.createOrReplaceTempView("incoming_properties_vw")
spark.sql(f"""
    MERGE INTO {CATALOG}.{DB}.silver_properties t
    USING incoming_properties_vw s ON t.prop_id = s.prop_id
    WHEN MATCHED AND s.scraped_at > t.scraped_at THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
""")

# ---------------------------------------------------------------------------
# silver_prices — one row per prop_id per date
# ---------------------------------------------------------------------------

raw_prices = _read_landing("prices")

w_price = Window.partitionBy("prop_id", "scraped_at").orderBy(F.desc("scraped_at"))

incoming_prices = (
    raw_prices
    .withColumn("row_num", F.row_number().over(w_price))
    .filter(F.col("row_num") == 1)
    .drop("row_num")
    .withColumn("scraped_at", F.col("scraped_at").cast("date"))
)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.silver_prices (
        prop_id INT,
        price INT,
        scraped_at DATE
    )
    USING iceberg
    TBLPROPERTIES ('format-version' = '2', 'write.target-file-size-bytes' = '134217728')
""")

incoming_prices.createOrReplaceTempView("incoming_prices_vw")
spark.sql(f"""
    MERGE INTO {CATALOG}.{DB}.silver_prices t
    USING incoming_prices_vw s ON t.prop_id = s.prop_id AND t.scraped_at = s.scraped_at
    WHEN NOT MATCHED THEN INSERT *
""")

# ---------------------------------------------------------------------------
# silver_spy_prices — one row per date
# ---------------------------------------------------------------------------

raw_spy = _read_landing("spy_prices")

w_spy = Window.partitionBy("date").orderBy(F.desc("loaded_at"))

incoming_spy = (
    raw_spy
    .withColumn("row_num", F.row_number().over(w_spy))
    .filter(F.col("row_num") == 1)
    .drop("row_num")
    .withColumn("date", F.col("date").cast("date"))
    .withColumn("loaded_at", F.col("loaded_at").cast("date"))
)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{DB}.silver_spy_prices (
        date DATE,
        close FLOAT,
        loaded_at DATE
    )
    USING iceberg
    TBLPROPERTIES ('format-version' = '2')
""")

incoming_spy.createOrReplaceTempView("incoming_spy_vw")
spark.sql(f"""
    MERGE INTO {CATALOG}.{DB}.silver_spy_prices t
    USING incoming_spy_vw s ON t.date = s.date
    WHEN NOT MATCHED THEN INSERT *
""")

job.commit()
