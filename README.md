# property-data-platform

End-to-end rental market data pipeline for 2-bed properties in SW London.

## Architecture

```
Rightmove / Bank of England / yfinance
        ↓
Databricks Serverless Job (scrape + geocode + financials)
        ↓
Lakeflow Declarative Pipeline (bronze → silver → gold)
        ↓
Delta tables on S3 (Unity Catalog)
        ↓
Streamlit dashboard (Streamlit Community Cloud)
```

**AWS infrastructure** managed by Terraform. **Databricks resources** (pipeline, job, schedule) managed by Databricks Asset Bundles.

## Repo structure

```
terraform/        # AWS: S3 bucket, IAM roles; Databricks: UC credential, secret scope
resources/        # DABs: pipeline.yml, job.yml
pipelines/        # Lakeflow: bronze.py, silver.py, gold.py
src/              # Python: scrape.py, financials.py
docs/             # Setup notes
```

## Resources

### AWS (managed by Terraform)

| Resource | Purpose |
|---|---|
| S3 bucket `property-data-platform-{account_id}` | Stores all Delta Lake tables (landing, bronze, silver, gold) |
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
| Lakeflow pipeline `property-data-platform-pipeline` | Serverless triggered pipeline — bronze ingest, silver dedup, gold aggregations |
| Job `property-data-platform-scrape` | Serverless job — scrapes Rightmove + financials, then triggers the pipeline |

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

### Testing the scraper

```bash
cd src
python scrape.py
```

This runs the full Rightmove scrape and prints a sample property and price record. No API keys or AWS credentials required — geocoding is skipped in local mode.

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

- **PR to main** — Terraform plan posted as PR comment; DABs bundle validated
- **Merge to main** — Terraform applied; DABs bundle deployed to prod

Changes to `terraform/**` only trigger Terraform workflows. Changes to `databricks.yml`, `resources/**`, `pipelines/**`, `src/**` only trigger the Databricks deploy workflow.
