resource "aws_secretsmanager_secret" "googlemaps_api_key" {
  name                    = "property-data-platform/GOOGLEMAPS_API_KEY"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "googlemaps_api_key" {
  secret_id     = aws_secretsmanager_secret.googlemaps_api_key.id
  secret_string = var.googlemaps_api_key
}
