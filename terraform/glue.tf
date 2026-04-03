locals {
  glue_scripts_path = "s3://${aws_s3_bucket.delta_lake.bucket}/glue-scripts"
  iceberg_path      = "s3://${aws_s3_bucket.delta_lake.bucket}/iceberg"
  landing_path      = "s3://${aws_s3_bucket.delta_lake.bucket}/landing"
}

# ---------------------------------------------------------------------------
# Glue Data Catalog
# ---------------------------------------------------------------------------

resource "aws_glue_catalog_database" "property_data" {
  name = "property_data"
}

# ---------------------------------------------------------------------------
# Glue Jobs
# ---------------------------------------------------------------------------

resource "aws_glue_job" "ingest" {
  name     = "property-data-platform-ingest"
  role_arn = aws_iam_role.glue_execution.arn

  # Python Shell (no Spark) — glue_version not set, not applicable for pythonshell
  command {
    name            = "pythonshell"
    python_version  = "3.9"
    script_location = "${local.glue_scripts_path}/ingest.py"
  }

  default_arguments = {
    "--landing_path"              = local.landing_path
    "--secret_name"               = aws_secretsmanager_secret.googlemaps_api_key.name
    "--additional-python-modules" = "requests,beautifulsoup4,yfinance,pandas,s3fs"
    "--extra-py-files"            = "${local.glue_scripts_path}/src/scrape.py"
    "--enable-job-insights"       = "false"
  }

  max_capacity = 0.0625 # cheapest Python Shell tier
  timeout      = 30     # minutes
}

resource "aws_glue_job" "ingest_spy" {
  name     = "property-data-platform-ingest-spy"
  role_arn = aws_iam_role.glue_execution.arn

  command {
    name            = "pythonshell"
    python_version  = "3.9"
    script_location = "${local.glue_scripts_path}/ingest_spy.py"
  }

  default_arguments = {
    "--landing_path"              = local.landing_path
    "--additional-python-modules" = "yfinance,pandas,s3fs"
    "--extra-py-files"            = "${local.glue_scripts_path}/src/financials.py"
    "--enable-job-insights"       = "false"
  }

  max_capacity = 0.0625
  timeout      = 15 # minutes
}

resource "aws_glue_job" "silver" {
  name         = "property-data-platform-silver"
  role_arn     = aws_iam_role.glue_execution.arn
  glue_version = "5.0"

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "${local.glue_scripts_path}/silver.py"
  }

  default_arguments = {
    "--landing_path"            = local.landing_path
    "--catalog_database"        = aws_glue_catalog_database.property_data.name
    "--job-bookmark-option"     = "job-bookmark-enable"
    "--enable-glue-datacatalog" = "true"
    "--datalake-formats"        = "iceberg"
    "--conf"                    = "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions --conf spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.glue_catalog.warehouse=${local.iceberg_path} --conf spark.sql.catalog.glue_catalog.type=glue"
  }

  number_of_workers = 2
  worker_type       = "G.1X"
  timeout           = 30 # minutes
}

resource "aws_glue_job" "gold" {
  name         = "property-data-platform-gold"
  role_arn     = aws_iam_role.glue_execution.arn
  glue_version = "5.0"

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "${local.glue_scripts_path}/gold.py"
  }

  default_arguments = {
    "--catalog_database"        = aws_glue_catalog_database.property_data.name
    "--enable-glue-datacatalog" = "true"
    "--datalake-formats"        = "iceberg"
    "--conf"                    = "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions --conf spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.glue_catalog.warehouse=${local.iceberg_path} --conf spark.sql.catalog.glue_catalog.type=glue"
  }

  number_of_workers = 2
  worker_type       = "G.1X"
  timeout           = 30 # minutes
}

# ---------------------------------------------------------------------------
# Glue Workflow — ingest → silver → gold
# ---------------------------------------------------------------------------

resource "aws_glue_workflow" "pipeline" {
  name = "property-data-platform"
}

resource "aws_glue_trigger" "ingest_on_demand" {
  name          = "property-data-platform-ingest-on-demand"
  type          = "ON_DEMAND"
  workflow_name = aws_glue_workflow.pipeline.name

  actions {
    job_name = aws_glue_job.ingest.name
  }
}

resource "aws_glue_trigger" "ingest_schedule" {
  name          = "property-data-platform-schedule"
  type          = "SCHEDULED"
  schedule      = "cron(0 7 ? * MON *)" # 07:00 UTC every Monday
  workflow_name = aws_glue_workflow.pipeline.name

  actions {
    job_name = aws_glue_job.ingest.name
  }
}

resource "aws_glue_trigger" "ingest_spy_schedule" {
  name          = "property-data-platform-ingest-spy-schedule"
  type          = "SCHEDULED"
  schedule      = "cron(0 7 ? * MON *)" # 07:00 UTC every Monday
  workflow_name = aws_glue_workflow.pipeline.name

  actions {
    job_name = aws_glue_job.ingest_spy.name
  }
}

resource "aws_glue_trigger" "silver_after_ingest" {
  name          = "property-data-platform-silver-trigger"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.pipeline.name

  predicate {
    conditions {
      job_name = aws_glue_job.ingest.name
      state    = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.silver.name
  }
}

resource "aws_glue_trigger" "gold_after_silver" {
  name          = "property-data-platform-gold-trigger"
  type          = "CONDITIONAL"
  workflow_name = aws_glue_workflow.pipeline.name

  predicate {
    conditions {
      job_name = aws_glue_job.silver.name
      state    = "SUCCEEDED"
    }
  }

  actions {
    job_name = aws_glue_job.gold.name
  }
}
