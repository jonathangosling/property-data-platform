variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# TODO: Remove databricks_host, databricks_token, databricks_account_id once Databricks resources are torn down.
variable "databricks_host" {
  description = "Databricks workspace URL (e.g. https://xxxxx.azuredatabricks.net)"
  type        = string
}

variable "databricks_token" {
  description = "Databricks personal access token"
  type        = string
  sensitive   = true
}

variable "databricks_account_id" {
  description = "Databricks account ID — used in Unity Catalog IAM trust policy"
  type        = string
}

variable "googlemaps_api_key" {
  description = "Google Maps API key for reverse geocoding"
  type        = string
  sensitive   = true
}
