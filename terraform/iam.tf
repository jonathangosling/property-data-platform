# Databricks UC IAM resources — commented out, Databricks decommissioned.
# Before deleting: run terraform state rm for null_resource, then
# terraform destroy -target for the IAM role and policy.

# resource "aws_iam_role" "unity_catalog_s3" {
#   name = "property-data-platform-uc-storage"
#
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Principal = {
#           AWS = "arn:aws:iam::414351767826:root"
#         }
#         Action = "sts:AssumeRole"
#         Condition = {
#           StringEquals = {
#             "sts:ExternalId" = var.databricks_account_id
#           }
#         }
#       }
#     ]
#   })
#
#   lifecycle {
#     ignore_changes = [assume_role_policy]
#   }
# }
#
# resource "null_resource" "unity_catalog_s3_self_trust" {
#   depends_on = [aws_iam_role.unity_catalog_s3]
#
#   triggers = {
#     role_arn = aws_iam_role.unity_catalog_s3.arn
#   }
#
#   provisioner "local-exec" {
#     command = <<-EOT
#       aws iam update-assume-role-policy \
#         --role-name ${aws_iam_role.unity_catalog_s3.name} \
#         --policy-document '{
#           "Version": "2012-10-17",
#           "Statement": [
#             {
#               "Effect": "Allow",
#               "Principal": { "AWS": "arn:aws:iam::414351767826:root" },
#               "Action": "sts:AssumeRole",
#               "Condition": { "StringEquals": { "sts:ExternalId": "${var.databricks_account_id}" } }
#             },
#             {
#               "Effect": "Allow",
#               "Principal": { "AWS": "${aws_iam_role.unity_catalog_s3.arn}" },
#               "Action": "sts:AssumeRole"
#             }
#           ]
#         }'
#     EOT
#   }
# }
#
# resource "aws_iam_role_policy" "unity_catalog_s3" {
#   name = "property-data-platform-s3-access"
#   role = aws_iam_role.unity_catalog_s3.id
#
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [{
#       Effect = "Allow"
#       Action = [
#         "s3:GetObject",
#         "s3:PutObject",
#         "s3:DeleteObject",
#         "s3:ListBucket",
#         "s3:GetBucketLocation"
#       ]
#       Resource = [
#         aws_s3_bucket.delta_lake.arn,
#         "${aws_s3_bucket.delta_lake.arn}/*"
#       ]
#     }]
#   })
# }

# Read-only IAM user for Streamlit dashboard to read gold Delta tables from S3.
resource "aws_iam_user" "streamlit_reader" {
  name = "property-data-platform-streamlit"
}

resource "aws_iam_user_policy" "streamlit_reader" {
  name = "property-data-platform-streamlit-read"
  user = aws_iam_user.streamlit_reader.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.delta_lake.arn,
          "${aws_s3_bucket.delta_lake.arn}/iceberg/*",
          "${aws_s3_bucket.delta_lake.arn}/athena-results/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartitions"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_access_key" "streamlit_reader" {
  user = aws_iam_user.streamlit_reader.name
}
