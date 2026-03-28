data "aws_caller_identity" "current" {}

# Main storage bucket — landing Parquet, Iceberg silver/gold tables, Glue scripts.
resource "aws_s3_bucket" "delta_lake" {
  bucket = "property-data-platform-${data.aws_caller_identity.current.account_id}"
}
