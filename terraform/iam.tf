# IAM role for Unity Catalog storage credential — allows Databricks to access S3.
# The self-referential trust statement is required for UC credential vending
# (allows the role to assume itself when passing credentials to cluster nodes).
resource "aws_iam_role" "unity_catalog_s3" {
  name = "property-data-platform-uc-storage"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::414351767826:root" # Databricks' AWS account
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "sts:ExternalId" = var.databricks_account_id
          }
        }
      },
      {
        # Self-referential trust required for Unity Catalog credential vending.
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/property-data-platform-uc-storage" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "unity_catalog_s3" {
  name = "property-data-platform-s3-access"
  role = aws_iam_role.unity_catalog_s3.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ]
      Resource = [
        aws_s3_bucket.delta_lake.arn,
        "${aws_s3_bucket.delta_lake.arn}/*"
      ]
    }]
  })
}

# Read-only IAM user for Streamlit dashboard to read gold Delta tables from S3.
resource "aws_iam_user" "streamlit_reader" {
  name = "property-data-platform-streamlit"
}

resource "aws_iam_user_policy" "streamlit_reader" {
  name = "property-data-platform-s3-read"
  user = aws_iam_user.streamlit_reader.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ]
      Resource = [
        aws_s3_bucket.delta_lake.arn,
        "${aws_s3_bucket.delta_lake.arn}/delta/gold_*"
      ]
    }]
  })
}

resource "aws_iam_access_key" "streamlit_reader" {
  user = aws_iam_user.streamlit_reader.name
}
