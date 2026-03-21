output "delta_lake_bucket" {
  description = "S3 bucket name for Delta Lake storage"
  value       = aws_s3_bucket.delta_lake.bucket
}

output "streamlit_access_key_id" {
  description = "AWS access key ID for Streamlit — add to Streamlit secrets"
  value       = aws_iam_access_key.streamlit_reader.id
}

output "streamlit_secret_access_key" {
  description = "AWS secret access key for Streamlit — add to Streamlit secrets"
  value       = aws_iam_access_key.streamlit_reader.secret
  sensitive   = true
}
