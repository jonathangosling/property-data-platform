"""
Scrape Rightmove property data and financial indicators, writing raw records
to Delta tables in S3 (landing zone). Runs as a Databricks Python script task.
"""
import argparse
import logging
from datetime import date, datetime, timedelta

import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from financials import get_interest_rates, get_spy_price
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

RIGHTMOVE_URL = (
    "https://www.rightmove.co.uk/property-to-rent/find.html"
    "?locationIdentifier=REGION%5E92829&maxBedrooms=2&minBedrooms=2"
    "&propertyTypes=&includeLetAgreed=false&mustHave=&dontShow="
    "&furnishTypes=&keywords="
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _chrome_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _accept_cookies(driver):
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
    except Exception:
        pass


def scrape_rightmove() -> list[dict]:
    """Scrape all pages of Rightmove listings. Returns list of raw records."""
    driver = _chrome_driver()
    records = []
    scraped_at = str(date.today())

    try:
        log.info("Navigating to Rightmove...")
        driver.get(RIGHTMOVE_URL)
        _accept_cookies(driver)

        button = driver.find_element(By.XPATH, "//button[@title='Next page']")
        pages = 0

        while True:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "propertyCard-anchor"))
            )
            for card in driver.find_elements(By.CLASS_NAME, "l-searchResult"):
                prop_id = int(
                    card.find_element(By.CLASS_NAME, "propertyCard-anchor")
                    .get_attribute("id")
                    .replace("prop", "")
                )
                price_text = card.find_element(By.CLASS_NAME, "propertyCard-priceValue").text
                price = int(price_text[1:-4].replace(",", ""))
                address = card.find_element(
                    By.CLASS_NAME, "propertyCard-address"
                ).get_attribute("title")
                records.append(
                    {"prop_id": prop_id, "price": price, "address": address, "scraped_at": scraped_at}
                )
            pages += 1

            button = driver.find_element(By.XPATH, "//button[@title='Next page']")
            if not button.is_enabled():
                break
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable(button))
            button.click()
            _accept_cookies(driver)

    finally:
        driver.quit()

    log.info(f"Scraped {len(records)} properties across {pages} pages.")
    return records


def geocode(address: str, api_key: str) -> dict:
    """Call Google Maps Geocoding API to get postcode and coordinates."""
    query = (address + ", London, UK").replace(" ", "%20")
    r = requests.get(
        f"https://maps.googleapis.com/maps/api/geocode/json?address={query}&key={api_key}"
    )
    r.raise_for_status()
    result = r.json()["results"][0]

    postcode = None
    for comp in result["address_components"]:
        if "postal_code" in comp["types"]:
            postcode = comp["long_name"]
            break

    return {
        "postcode": postcode,
        "latitude": round(result["geometry"]["location"]["lat"], 8),
        "longitude": round(result["geometry"]["location"]["lng"], 8),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(s3_bucket: str, googlemaps_api_key: str):
    spark = SparkSession.builder.getOrCreate()
    today = date.today()

    # --- Properties & prices ---
    log.info("Scraping Rightmove...")
    raw = scrape_rightmove()

    log.info("Geocoding addresses...")
    properties, prices = [], []
    seen_props = set()
    for rec in raw:
        geo = geocode(rec["address"], googlemaps_api_key)
        if rec["prop_id"] not in seen_props:
            seen_props.add(rec["prop_id"])
            properties.append({
                "prop_id": rec["prop_id"],
                "address": rec["address"],
                "postcode": geo["postcode"],
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "scraped_at": rec["scraped_at"],
            })
        prices.append({
            "prop_id": rec["prop_id"],
            "date": str(today),
            "price": rec["price"],
            "scraped_at": rec["scraped_at"],
        })

    (
        spark.createDataFrame(properties)
        .write.format("delta")
        .mode("append")
        .save(f"s3://{s3_bucket}/landing/properties")
    )
    (
        spark.createDataFrame(prices)
        .write.format("delta")
        .mode("append")
        .save(f"s3://{s3_bucket}/landing/prices")
    )
    log.info(f"Written {len(properties)} properties and {len(prices)} prices.")

    # --- Interest rates ---
    log.info("Fetching interest rate data...")
    rates = get_interest_rates(today - timedelta(days=7), today)
    if rates:
        (
            spark.createDataFrame(rates)
            .write.format("delta")
            .mode("append")
            .save(f"s3://{s3_bucket}/landing/interest_rates")
        )

    # --- SPY price ---
    log.info("Fetching SPY price...")
    spy = get_spy_price()
    if spy:
        (
            spark.createDataFrame([spy])
            .write.format("delta")
            .mode("append")
            .save(f"s3://{s3_bucket}/landing/spy_prices")
        )

    log.info("Scrape job complete.")


if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-bucket", required=True)
    args = parser.parse_args()

    main(
        s3_bucket=args.s3_bucket,
        googlemaps_api_key=os.environ["GOOGLEMAPS_API_KEY"],
    )
