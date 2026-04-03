resource "aws_glue_data_quality_ruleset" "silver_properties" {
  name = "silver-properties-dq"

  ruleset = <<-DQDL
    Rules = [
      RowCount > 500,
      IsComplete "prop_id",
      IsComplete "address",
      IsComplete "latitude",
      IsComplete "longitude",
      IsUnique "prop_id",
      Completeness "postcode" >= 0.9,
      CustomSql "SELECT COUNT_IF(area_code IS NULL OR area_code NOT LIKE 'SW%') * 1.0 / COUNT(*) FROM primary" < 0.1
    ]
  DQDL

  target_table {
    database_name = aws_glue_catalog_database.property_data.name
    table_name    = "silver_properties"
  }
}

resource "aws_glue_data_quality_ruleset" "silver_prices" {
  name = "silver-prices-dq"

  ruleset = <<-DQDL
    Rules = [
      RowCount > 500,
      IsComplete "prop_id",
      IsComplete "price",
      IsComplete "date",
      ColumnValues "price" between 100 and 50000
    ]
  DQDL

  target_table {
    database_name = aws_glue_catalog_database.property_data.name
    table_name    = "silver_prices"
  }
}

resource "aws_glue_data_quality_ruleset" "silver_spy_prices" {
  name = "silver-spy-prices-dq"

  ruleset = <<-DQDL
    Rules = [
      RowCount > 0,
      IsComplete "date",
      IsComplete "close",
      ColumnValues "close" > 0,
      IsUnique "date"
    ]
  DQDL

  target_table {
    database_name = aws_glue_catalog_database.property_data.name
    table_name    = "silver_spy_prices"
  }
}

resource "aws_glue_data_quality_ruleset" "gold_current_properties" {
  name = "gold-current-properties-dq"

  ruleset = <<-DQDL
    Rules = [
      RowCount > 400,
      IsComplete "prop_id",
      IsComplete "price",
      IsComplete "area_code",
      ColumnValues "price" between 100 and 50000
    ]
  DQDL

  target_table {
    database_name = aws_glue_catalog_database.property_data.name
    table_name    = "gold_current_properties"
  }
}

resource "aws_glue_data_quality_ruleset" "gold_property_fact" {
  name = "gold-property-fact-dq"

  ruleset = <<-DQDL
    Rules = [
      RowCount > 0,
      IsComplete "area_code",
      IsComplete "avg_price",
      ColumnValues "avg_price" between 500 and 20000,
      ColumnValues "num_properties" > 0
    ]
  DQDL

  target_table {
    database_name = aws_glue_catalog_database.property_data.name
    table_name    = "gold_property_fact"
  }
}
