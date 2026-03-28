variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# variable "databricks_host"        { ... }  # decommissioned
# variable "databricks_token"        { ... }  # decommissioned
# variable "databricks_account_id"   { ... }  # decommissioned

variable "googlemaps_api_key" {
  description = "Google Maps API key for reverse geocoding"
  type        = string
  sensitive   = true
}
