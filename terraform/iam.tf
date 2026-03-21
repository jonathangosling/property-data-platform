# IAM role for Databricks cluster nodes to access S3.
# After apply, register as an instance profile in Databricks workspace UI:
# Workspace settings → Instance profiles → Add → paste instance_profile_arn output.
resource "aws_iam_role" "databricks_s3" {
  name = "property-data-platform-databricks-s3"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "databricks_s3" {
  name = "property-data-platform-s3-access"
  role = aws_iam_role.databricks_s3.id

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

resource "aws_iam_instance_profile" "databricks_s3" {
  name = "property-data-platform-databricks-s3"
  role = aws_iam_role.databricks_s3.name
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
        "${aws_s3_bucket.delta_lake.arn}/delta/property_data/gold_*"
      ]
    }]
  })
}

resource "aws_iam_access_key" "streamlit_reader" {
  user = aws_iam_user.streamlit_reader.name
}
