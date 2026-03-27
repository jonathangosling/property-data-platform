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

## Glue Data Quality

Glue Data Quality (DQDL) can be used to add data quality expectations to silver tables, replacing the DLT `@dlt.expect` annotations. Worth adding once the pipeline is stable.
