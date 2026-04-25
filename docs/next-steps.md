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

## London expansion

Extending coverage to all central London postcodes (E, EC, N, NW, SE, SW, W, WC).

**Rightmove region code:** `5E87490` (generic London region — covers all postcodes)

**EC/WC sub-district normalisation:** EC and WC postcodes include a trailing letter in the district segment (e.g. `EC1A`, `EC2V`). These must be normalised to `EC1`, `EC2`, etc. for area-level aggregation. Same applies to W1 and SW1. Use `regexp_extract` to strip the trailing letter:

```sql
regexp_extract(substring_index(postcode, ' ', 1), '^([A-Z]{1,2}\\d+)', 1) AS area_code
```

**Geocoding cost:** Google Maps Geocoding API has a free tier of 10,000 requests/month. At ~10,000 properties/week that's ~40,000 requests/month — roughly 30,000 paid requests at ~£3.75/1,000 = **~£112/month**. This makes the current approach (geocode every property on every scrape) uneconomical at London scale.

**Preferred geocoding approach: postcodes.io**

[postcodes.io](https://postcodes.io) is a free, open-source UK postcode API with no API key required. It supports bulk reverse geocoding via `POST /postcodes` — up to 100 lat/lng pairs per request — returning the nearest postcode for each point. This replaces Google Maps entirely for the postcode lookup use case and reduces geocoding cost to zero. At 10,000 properties, that's 100 batch requests instead of 10,000 individual ones.

**Option: only geocode new properties (move geocoding to silver)**

Rather than geocoding in ingest, geocoding can be deferred to the silver step:

1. `ingest.py` writes raw properties with `lat`/`lng` to landing but no postcode.
2. `silver.py` reads incoming prop_ids, LEFT JOINs against `silver_properties` to identify which prop_ids are new (no existing postcode).
3. Only new properties are sent to the Geocoding API.
4. The postcode is included in the MERGE so it's written once and never re-geocoded.

This reduces API calls to net-new listings only — churn will be a fraction of the full 10K weekly scrape. The trade-off is that silver becomes stateful (must read existing silver before writing) and geocoding failures on the silver job are harder to retry than in the simpler ingest flow.
