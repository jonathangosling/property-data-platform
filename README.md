# property-data-platform

End-to-end rental market data pipeline for 2-bed properties in SW London.

## Architecture

```
Rightmove / Bank of England / yfinance
        ↓
Databricks Job — spot cluster (scrape + geocode + financials)
        ↓  writes Delta tables to S3 landing zone
Lakeflow Declarative Pipeline — serverless (silver → gold)
        ↓
Delta tables on S3 (Unity Catalog)
        ↓
Streamlit dashboard (Streamlit Community Cloud)
```

**AWS infrastructure** managed by Terraform. **Databricks resources** (pipeline, job, schedule) managed by Databricks Asset Bundles.

## Repo structure

```
terraform/                        # AWS: S3 bucket, IAM roles; Databricks: UC credential, secret scope
resources/                        # DABs: pipeline.yml, job.yml
pipelines/                        # Lakeflow: silver.py, gold.py
src/
  property_data_platform/         # Python wheel package
    __init__.py
    scrape.py                     # Rightmove scraper + reverse geocoder
    financials.py                 # BoE interest rates + SPY price
    ingest.py                     # Job entry point — orchestrates scrape and Delta writes
setup.py                          # Wheel build config (entry point: ingest)
docs/                             # Setup notes
```

## Resources

### AWS (managed by Terraform)

| Resource | Purpose |
|---|---|
| S3 bucket `property-data-platform-{account_id}` | Stores all Delta Lake tables (landing, silver, gold) |
| IAM role `property-data-platform-uc-storage` | Assumed by Databricks Unity Catalog to read/write the S3 bucket |
| IAM user `property-data-platform-streamlit` | Read-only access to gold Delta tables for the Streamlit dashboard |

### Databricks (managed by Terraform)

| Resource | Purpose |
|---|---|
| Storage credential `property-data-platform-s3` | Registers the UC IAM role with Databricks so pipelines can access S3 |
| External location `property-data-platform` | Exposes the S3 bucket as a Unity Catalog managed path |
| Secret scope `property-data-platform` | Stores application secrets (API keys) |
| Secret `GOOGLEMAPS_API_KEY` | Google Maps API key injected into the scrape job at runtime |

### Databricks (managed by Asset Bundles)

| Resource | Purpose |
|---|---|
| Lakeflow pipeline `property-data-platform-pipeline` | Serverless triggered pipeline — silver dedup, gold aggregations |
| Job `property-data-platform-scrape` | Spot cluster job — scrapes Rightmove + financials, writes landing Delta tables, then triggers the pipeline |

### Databricks (auto-provisioned)

| Resource | Purpose |
|---|---|
| Workspace | Databricks workspace provisioned via AWS Marketplace |
| Unity Catalog metastore `metastore_aws_us_east_1` | Account-level metastore managing table schemas and storage credentials |
| Workspace storage bucket | Databricks-managed S3 bucket for workspace assets (notebooks, logs) |

### External services

| Service | Purpose |
|---|---|
| Rightmove | Source of property listing data (scraped via requests + BeautifulSoup) |
| Google Maps Geocoding API | Reverse geocodes Rightmove coordinates to postcodes |
| Bank of England API | SONIA interest rate data |
| yfinance | SPY ETF close price (S&P 500 proxy) |
| Streamlit Community Cloud | Free public dashboard hosting |

## Local development

### Setup

```bash
cd property-data-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Unit tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

Tests cover `_parse_page` in `scrape.py` — the core parsing logic including the failure rate threshold. External API calls (Rightmove, Google Maps, BoE, yfinance) are not mocked as tests against live structure add little value and require credentials.

Tests also run in CI on every push and PR that touches `src/**` or `tests/**`, and must pass before deploy.

### Testing the scraper end-to-end

```bash
PYTHONPATH=src python src/scrape.py
```

Runs the full Rightmove scrape and prints a sample property and price record. No API keys or AWS credentials required — geocoding is skipped in local mode.

### Dry run (full pipeline without S3 writes)

```bash
source .env && PYTHONPATH=src python glue/ingest.py --landing_path anything --secret_name anything --dry-run
```

Runs the full ingest — scrape, geocode, and financial data fetch — but skips the S3 writes. Logs a summary of what would be written. Requires `GOOGLEMAPS_API_KEY` in `.env` for geocoding (omit to skip postcodes). No AWS credentials needed.

## Deployment

### Prerequisites

1. Terraform applied — S3 bucket, IAM roles, UC storage credential, and secret scope provisioned
2. Databricks workspace set up with Unity Catalog metastore attached
3. GitHub Actions secrets configured:

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS credentials for Terraform |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Terraform |
| `TF_STATE_BUCKET` | Shared Terraform state S3 bucket |
| `TF_LOCK_TABLE` | Shared Terraform state DynamoDB lock table |
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | Personal access token |
| `DATABRICKS_ACCOUNT_ID` | Databricks account ID (used in UC IAM trust policy) |
| `S3_BUCKET` | Delta Lake bucket name (Terraform output) |
| `GOOGLEMAPS_API_KEY` | Google Maps API key for reverse geocoding |

### Databricks Personal Access Token

The `DATABRICKS_TOKEN` secret is a Databricks PAT with a 90-day lifetime. To generate or rotate it:

1. Log into the Databricks workspace → click your username (top right) → **User Settings**
2. **Developer → Access tokens → Manage → Generate new token**
3. Set a 90-day lifetime, copy the token
4. Update the `DATABRICKS_TOKEN` secret in GitHub: repo → **Settings → Secrets and variables → Actions**

Set a calendar reminder before the 90-day expiry — CI/CD will fail silently if the token expires without being rotated.

### CI/CD

- **PR to main** — unit tests run; Terraform plan posted as PR comment; DABs bundle validated
- **Merge to main** — unit tests run; Terraform applied; DABs bundle deployed to prod (blocked if tests fail)

Changes to `terraform/**` only trigger Terraform workflows. Changes to `databricks.yml`, `setup.py`, `resources/**`, `pipelines/**`, `src/**` only trigger the Databricks deploy workflow.

## Delta tables

### Landing (written by the scrape job)

| Table | S3 path | Description |
|---|---|---|
| `landing/properties` | `s3://{bucket}/landing/properties` | Raw property records from Rightmove, partitioned by `scraped_at` |
| `landing/prices` | `s3://{bucket}/landing/prices` | Raw price records from Rightmove |
| `landing/spy_prices` | `s3://{bucket}/landing/spy_prices` | SPY ETF close prices |

### Pipeline (managed by Unity Catalog, registered under `main.property_data`)

| Table | Description |
|---|---|
| `silver_properties` | Deduplicated property dimension — one row per `prop_id` |
| `silver_prices` | Deduplicated price fact — one row per `prop_id` per date |
| `silver_spy_prices` | Deduplicated SPY prices — one row per date |
| `gold_property_fact` | Avg/median price and count by date and SW area code, with month and year columns |
| `gold_current_properties` | Snapshot of listings on the most recent scrape date |
| `gold_area_dim` | SW London area code to district name mapping |

### Portability

Silver and gold tables are UC-managed (serverless pipelines require UC). If you ever need to move data to Glue/Athena or another platform, create external copies with a CTAS:

```sql
CREATE TABLE glue_db.silver_properties
LOCATION 's3://your-bucket/glue/silver_properties'
AS SELECT * FROM main.property_data.silver_properties;
```

The landing tables are already at known S3 paths and can be registered directly in Glue without any data movement:

```sql
CREATE EXTERNAL TABLE glue_db.landing_properties
LOCATION 's3://your-bucket/landing/properties'
STORED AS PARQUET TBLPROPERTIES ('parquet.compress'='SNAPPY');
```
