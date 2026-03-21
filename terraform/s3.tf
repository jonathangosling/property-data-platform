data "aws_caller_identity" "current" {}

# Delta Lake storage bucket — holds all bronze/silver/gold Delta tables.
resource "aws_s3_bucket" "delta_lake" {
  bucket = "property-data-platform-${data.aws_caller_identity.current.account_id}"
}
