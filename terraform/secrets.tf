resource "aws_secretsmanager_secret" "googlemaps_api_key" {
  name                    = "property-data-platform/GOOGLEMAPS_API_KEY"
  recovery_window_in_days = 0
}
