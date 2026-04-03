# property-data-platform

End-to-end rental market data pipeline for 2-bed properties in SW London.

## Architecture

```
Rightmove / yfinance
        ↓
AWS Glue Python Shell — ingest + ingest_spy
        ↓  writes Parquet files to S3 landing zone
AWS Glue ETL (Spark) — silver → gold
        ↓
Iceberg tables on S3 (Glue Data Catalog)
        ↓
Streamlit dashboard (Streamlit Community Cloud)
```

**AWS infrastructure** managed by Terraform. **Glue scripts** deployed to S3 via GitHub Actions.

## Repo structure

```
glue/
  ingest.py       # Python Shell — scrapes Rightmove + geocodes, writes landing Parquet
  ingest_spy.py   # Python Shell — fetches SPY prices, writes landing Parquet
  silver.py       # Glue ETL (Spark) — deduplicates landing into Iceberg silver tables
  gold.py         # Glue ETL (Spark) — aggregates silver into Iceberg gold tables
src/
  scrape.py       # Rightmove scraper + reverse geocoder (used by ingest)
  financials.py   # yfinance SPY price fetch (used by ingest_spy)
terraform/        # AWS: S3, IAM, Glue jobs, Glue workflow, Secrets Manager
tests/
  test_scrape.py  # Unit tests for scrape.py
```

## Resources

### AWS (managed by Terraform)

| Resource | Purpose |
|---|---|
| S3 bucket `property-data-platform-{account_id}` | Landing Parquet files, Iceberg tables, Glue scripts |
| IAM role `property-data-platform-glue-execution` | Assumed by Glue jobs to read/write S3 and Glue catalog |
| Glue Data Catalog database `property_data` | Metastore for Iceberg silver and gold tables |
| Glue job `property-data-platform-ingest` | Python Shell — scrape + geocode |
| Glue job `property-data-platform-ingest-spy` | Python Shell — SPY price fetch |
| Glue job `property-data-platform-silver` | Glue ETL — silver layer |
| Glue job `property-data-platform-gold` | Glue ETL — gold layer |
| Glue workflow `property-data-platform` | Orchestrates ingest → silver → gold |
| Secrets Manager secret `property-data-platform/GOOGLEMAPS_API_KEY` | Google Maps API key injected into ingest at runtime |

### External services

| Service | Purpose |
|---|---|
| Rightmove | Source of property listing data (scraped via requests + BeautifulSoup) |
| Google Maps Geocoding API | Reverse geocodes Rightmove coordinates to postcodes |
| yfinance | SPY ETF close price (S&P 500 proxy) |
| Streamlit Community Cloud | Free public dashboard hosting |

## Glue workflow

```
ingest (Monday 07:00 UTC)
    → silver (runs on ingest SUCCEEDED)
        → gold (runs on silver SUCCEEDED)

ingest_spy (Monday 07:00 UTC, independent)
```

Both jobs run weekly on Monday morning. Monday captures weekend listing activity — landlords and agents tend to list on Fridays and weekends, so Monday gives a fresh snapshot. It also ensures the prior week's SPY close prices are available from yfinance before ingest_spy runs.

The workflow can also be triggered on demand via the Glue console or `aws glue start-workflow-run`.

## Local development

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Unit tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

Tests cover `_parse_page` and `add_postcodes` in `scrape.py` — parsing logic, failure rate threshold, and postcode missing rate threshold. External API calls are not tested.

### Smoke test the scraper

```bash
PYTHONPATH=src python src/scrape.py
```

Runs the full Rightmove scrape and prints a sample property and price record. No API key or AWS credentials required — geocoding is skipped.

### Dry run ingest

```bash
source .env && PYTHONPATH=src python glue/ingest.py --landing_path any --secret_name any --dry-run
```

Runs scrape and geocode but skips S3 writes. Requires `GOOGLEMAPS_API_KEY` in `.env`. No AWS credentials needed.

```bash
PYTHONPATH=src python glue/ingest_spy.py --landing_path any --dry-run
```

Fetches 7 days of SPY prices and logs what would be written. No AWS credentials needed.

## Deployment

### Prerequisites

1. Terraform applied — S3 bucket, IAM roles, Glue jobs, and Glue workflow provisioned
2. Google Maps API key stored manually in Secrets Manager under `property-data-platform/GOOGLEMAPS_API_KEY`
3. GitHub Actions secrets configured:

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS credentials for Terraform and S3 deploy |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Terraform and S3 deploy |
| `TF_STATE_BUCKET` | Shared Terraform state S3 bucket |
| `TF_LOCK_TABLE` | Shared Terraform state DynamoDB lock table |
| `S3_BUCKET` | Data platform S3 bucket name (Terraform output) |

### CI/CD

Two workflows:

**`glue-deploy.yml`** — triggered on changes to `glue/**`, `src/**`, or `tests/**`:
- PRs: runs unit tests only
- Merge to main: runs unit tests, then uploads all Glue scripts to `s3://{bucket}/glue-scripts/`

**`tf-apply.yml`** — triggered on changes to `terraform/**` merged to main:
- Runs `terraform apply -auto-approve`

## Data quality

### Ingest checks (fail the job)

These checks run during ingestion and raise a `RuntimeError` to fail the Glue job if breached:

| Job | Check | Threshold |
|---|---|---|
| `ingest` | Parse failure rate — fraction of Rightmove property records that fail to parse | > 10% |
| `ingest` | Missing postcode rate — fraction of properties with no postcode after reverse geocoding | > 10% |
| `ingest_spy` | No SPY records returned from yfinance | 0 records |

### Glue Data Quality rulesets (on-demand)

Rulesets are defined in Terraform and registered against each Glue catalog table. They can be run from the Glue console (Data Catalog → table → Data Quality tab) or via the AWS CLI.

| Table | Rules |
|---|---|
| `silver_properties` | RowCount > 500, prop_id complete and unique, address/lat/lng complete, postcode completeness ≥ 90%, ≥ 90% of area codes match `SW*` |
| `silver_prices` | RowCount > 500, prop_id/price/date complete, price between £100–£50,000 |
| `silver_spy_prices` | RowCount > 0, date/close complete and unique, close > 0 |
| `gold_current_properties` | RowCount > 400, prop_id/price/area_code complete, price between £100–£50,000 |
| `gold_property_fact` | RowCount > 0, area_code/avg_price complete, avg_price between £500–£20,000, num_properties > 0 |

## Tables

### Landing (Parquet, written by ingest jobs)

| Path | Description |
|---|---|
| `s3://{bucket}/landing/properties/` | Raw property records from Rightmove |
| `s3://{bucket}/landing/prices/` | Raw price records from Rightmove |
| `s3://{bucket}/landing/spy_prices/` | SPY ETF close prices |

### Silver (Iceberg, deduplicated)

| Table | Description |
|---|---|
| `silver_properties` | One row per `prop_id` — latest scrape wins |
| `silver_prices` | One row per `prop_id` per date |
| `silver_spy_prices` | One row per date |

### Gold (Iceberg, aggregated)

| Table | Description |
|---|---|
| `gold_property_fact` | Avg/median price and count by date and SW area code |
| `gold_current_properties` | All listings on the most recent scrape date |
| `gold_area_dim` | SW London area code to district name mapping |
