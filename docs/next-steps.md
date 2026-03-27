# Next Steps

## Databricks decommission

Databricks was decommissioned due to persistent NAT Gateway charges (~£30/month) from the Databricks-managed VPC. Migrated to AWS Glue + Iceberg.

The original plan was to fix the wheel installation issue by switching landing tables from S3 Delta to a UC Volume (`/Volumes/main/property_data/landing`), and to adopt DLT streaming tables with `APPLY CHANGES INTO` for incremental silver processing. This was superseded by the Glue migration.

**Remaining cleanup:**

- Delete `databricks.yml`, `resources/`, `pipelines/` directories
- Delete `.github/workflows/databricks-deploy.yml`
- Delete `terraform/databricks.tf` and remove Databricks providers/variables
- Remove GitHub Actions secrets: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_ACCOUNT_ID`

## Iceberg snapshot expiry

Snapshots are kept forever by default — storage cost will accumulate over time. Fix by adding to each silver/gold table's TBLPROPERTIES:

```sql
'history.expire.max-snapshot-age-ms' = '604800000'  -- 7 days
```

This triggers automatic expiry on each write with no extra infrastructure.

## FRED API for interest rates

Interest rate data (BoE SONIA) was removed. To be re-added via FRED API — requires a free API key from fred.stlouisfed.org.

## Iceberg Spark config (if needed)

If the Glue ETL jobs fail to resolve the `glue_catalog` catalog, the full explicit Spark conf is:

```
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.glue_catalog.warehouse=s3://{bucket}/iceberg
spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog
spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO
```

Add as `--conf` in `glue.tf` for the silver and gold jobs.

## Glue Data Quality

Glue Data Quality (DQDL) can be used to add data quality expectations to silver tables, replacing the DLT `@dlt.expect` annotations. Worth adding once the pipeline is stable.

Suggested rules for `silver_properties`:
- `IsComplete "postcode"` — flag null postcodes (geocoding failures)
- `IsComplete "prop_id"` — no null IDs
- `CustomSql "SELECT COUNT_IF(area_code IS NULL OR area_code NOT IN ('SW1','SW2',...)) / COUNT(*) FROM primary < 0.05"` — alert if more than 5% of properties are outside SW area codes, which would indicate a geocoding issue or a change to the Rightmove search results
