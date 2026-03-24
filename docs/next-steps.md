# Next Steps

## Current blocker — wheel installation failing

The scrape job fails to install the Python wheel because `data_security_mode: SINGLE_USER` (needed for S3 access) also restricts the cluster from reading wheel files from `/Workspace/`.

### Agreed fix: switch to UC Volume for landing tables

Instead of writing Delta tables directly to S3 (`s3://property-data-platform-517574620103/landing/...`), write via a UC Volume. UC handles S3 credentials transparently — no `SINGLE_USER` needed.

**Changes required:**

1. **Terraform** — create an external volume backed by the S3 bucket:
   ```hcl
   resource "databricks_volume" "landing" {
     catalog_name     = "main"
     schema_name      = "property_data"
     name             = "landing"
     volume_type      = "EXTERNAL"
     storage_location = "s3://property-data-platform-517574620103/landing"
   }
   ```
   Note: `property_data` schema is created by the DLT pipeline — it must exist before Terraform can create the volume. Either run the pipeline once first, or create the schema in Terraform too.

2. **`resources/job.yml`** — remove `data_security_mode: SINGLE_USER`

3. **`databricks.yml`** — remove `experimental.python_wheel_wrapper: true`

4. **`src/property_data_platform/ingest.py`** — change base path from `s3://{bucket}/landing` to `/Volumes/main/property_data/landing`. The `--s3-bucket` argument can be removed.

5. **`pipelines/silver.py`** — change all `spark.read.format("delta").load(f"s3://{S3_BUCKET}/landing/...")` to `/Volumes/main/property_data/landing/...`. The `s3_bucket` pipeline config can be removed.

6. **`resources/pipeline.yml`** — remove the `s3_bucket` configuration parameter.

7. **`databricks.yml`** — remove the `s3_bucket` variable.

## Silver layer streaming tables

Currently silver reads the entire landing Delta table on every pipeline run and deduplicates with a window function. As landing tables grow this gets slower and more expensive.

Switch to DLT streaming tables + `APPLY CHANGES INTO` so silver only processes new records from each ingest run:

```python
dlt.create_streaming_table("silver_properties")

dlt.apply_changes(
    target="silver_properties",
    source="landing_properties_stream",  # landing table read as stream
    keys=["prop_id"],
    sequence_by="scraped_at",
)
```

Delta Lake tracks commits in the transaction log — DLT checkpoints the last processed commit and only reads new appends on each run. Works cleanly with our `mode("append")` ingest writes.

Prerequisite: landing tables should be registered as external Delta tables in Unity Catalog so DLT can use them as streaming sources. This falls out naturally from the volume migration above.

## Other notes

- Interest rate data (BoE SONIA) was removed — to be re-added later via FRED API (requires a free API key from fred.stlouisfed.org)
- `python_wheel_wrapper: true` is currently in `databricks.yml` as a temporary measure — remove once the volume fix is in place
- Silver/gold pipeline improvements done: area_code moved to silver, dates cast to DateType, `.collect()` replaced with window function
