# TODO: Remove unity_catalog_s3 role, null_resource.unity_catalog_s3_self_trust, and
# aws_iam_role_policy.unity_catalog_s3 — Databricks decommissioned, migrating to AWS Glue.
# Replace with a Glue execution role (see glue.tf once created).

# IAM role for Unity Catalog storage credential — allows Databricks to access S3.
# Created without the self-referential trust (AWS rejects forward references to roles
# that don't exist yet). The self-referential trust is added after creation via
# null_resource below, as required by Unity Catalog.
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
      }
    ]
  })

  lifecycle {
    ignore_changes = [assume_role_policy]
  }
}

# Adds the self-referential trust statement after the role exists.
# Required by Unity Catalog for credential vending.
resource "null_resource" "unity_catalog_s3_self_trust" {
  depends_on = [aws_iam_role.unity_catalog_s3]

  triggers = {
    role_arn = aws_iam_role.unity_catalog_s3.arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws iam update-assume-role-policy \
        --role-name ${aws_iam_role.unity_catalog_s3.name} \
        --policy-document '{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": { "AWS": "arn:aws:iam::414351767826:root" },
              "Action": "sts:AssumeRole",
              "Condition": { "StringEquals": { "sts:ExternalId": "${var.databricks_account_id}" } }
            },
            {
              "Effect": "Allow",
              "Principal": { "AWS": "${aws_iam_role.unity_catalog_s3.arn}" },
              "Action": "sts:AssumeRole"
            }
          ]
        }'
    EOT
  }
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
        "${aws_s3_bucket.delta_lake.arn}/iceberg/gold_*"
      ]
    }]
  })
}

resource "aws_iam_access_key" "streamlit_reader" {
  user = aws_iam_user.streamlit_reader.name
}
