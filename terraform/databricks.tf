# Databricks decommissioned — resources commented out pending state cleanup.
# Before removing, run:
#   terraform state rm databricks_storage_credential.delta_lake
#   terraform state rm databricks_external_location.delta_lake
#   terraform state rm databricks_secret_scope.main
#   terraform state rm databricks_secret.googlemaps_api_key
#   terraform state rm time_sleep.wait_for_iam_propagation

# resource "time_sleep" "wait_for_iam_propagation" {
#   depends_on      = [null_resource.unity_catalog_s3_self_trust]
#   create_duration = "30s"
# }

# resource "databricks_storage_credential" "delta_lake" {
#   name = "property-data-platform-s3"
#   aws_iam_role {
#     role_arn = aws_iam_role.unity_catalog_s3.arn
#   }
#   comment    = "Storage credential for Delta Lake bucket"
#   depends_on = [time_sleep.wait_for_iam_propagation]
# }

# resource "databricks_external_location" "delta_lake" {
#   name            = "property-data-platform"
#   url             = "s3://${aws_s3_bucket.delta_lake.bucket}"
#   credential_name = databricks_storage_credential.delta_lake.id
#   comment         = "Delta Lake storage for property-data-platform"
# }

# resource "databricks_secret_scope" "main" {
#   name = "property-data-platform"
# }

# resource "databricks_secret" "googlemaps_api_key" {
#   key          = "GOOGLEMAPS_API_KEY"
#   string_value = var.googlemaps_api_key
#   scope        = databricks_secret_scope.main.id
# }
