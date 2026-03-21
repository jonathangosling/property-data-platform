"""
Scrape Rightmove property listings using requests + BeautifulSoup.

Extracts data from the __NEXT_DATA__ JSON blob embedded in the HTML —
more reliable than parsing CSS class names which are hashed and change frequently.
Coordinates are taken directly from Rightmove. Postcodes are obtained via
reverse geocoding (lat/long → postcode) using the Google Maps API, which is
more accurate than forward geocoding from an address string.
Pagination is driven dynamically from the JSON so no page size is hardcoded.

Entry point for the Databricks job: accepts --s3-bucket, reads the Google Maps
API key from Databricks secrets, and writes landing JSON files to S3.
"""
import logging
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = (
    "https://www.rightmove.co.uk/property-to-rent/find.html"
    "?locationIdentifier=REGION%5E92829"
    "&maxBedrooms=2&minBedrooms=2"
    "&propertyTypes=&includeLetAgreed=false"
    "&mustHave=&dontShow=&furnishTypes=&keywords="
)

# Generic browser User-Agent — avoids the default python-requests string
# which is commonly blocked. Does not need to match the running machine.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# If more than this fraction of property records on a page fail to parse,
# raise an error — likely indicates a structural change to Rightmove's JSON.
PARSE_FAILURE_THRESHOLD = 0.1


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _fetch_next_data(session: requests.Session, index: int) -> dict:
    """Fetch a Rightmove page and return the parsed __NEXT_DATA__ JSON."""
    url = BASE_URL if index == 0 else f"{BASE_URL}&index={index}"
    r = session.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        raise RuntimeError(
            f"__NEXT_DATA__ not found at index={index}. "
            "Rightmove may have changed their page structure."
        )
    return json.loads(script.string)


def _get_search_results(data: dict) -> dict:
    """Navigate to the search results within __NEXT_DATA__."""
    try:
        return data["props"]["pageProps"]["searchResults"]
    except KeyError:
        raise RuntimeError(
            "Could not find props.pageProps.searchResults in __NEXT_DATA__. "
            "Rightmove may have changed their data structure."
        )


def _parse_page(
    search_results: dict, scraped_at: str, page_index: int
) -> tuple[list[dict], list[dict]]:
    """
    Extract property and price records from a page's search results.
    Raises if the parse failure rate exceeds PARSE_FAILURE_THRESHOLD.
    """
    raw_properties = search_results.get("properties", [])
    if not raw_properties:
        raise RuntimeError(
            f"No properties found at index={page_index}. "
            "Rightmove may have changed their data structure."
        )

    properties, prices = [], []
    failures = 0

    for prop in raw_properties:
        try:
            prop_id = int(prop["id"])
            price = int(prop["price"]["amount"])
            address = prop["displayAddress"]
            lat = round(float(prop["location"]["latitude"]), 8)
            lng = round(float(prop["location"]["longitude"]), 8)

            properties.append({
                "prop_id": prop_id,
                "address": address,
                "latitude": lat,
                "longitude": lng,
                "scraped_at": scraped_at,
            })
            prices.append({
                "prop_id": prop_id,
                "date": scraped_at,
                "price": price,
                "scraped_at": scraped_at,
            })
        except (KeyError, ValueError, TypeError):
            failures += 1

    failure_rate = failures / len(raw_properties)
    if failure_rate > PARSE_FAILURE_THRESHOLD:
        raise RuntimeError(
            f"Parse failure rate {failure_rate:.0%} exceeds threshold "
            f"{PARSE_FAILURE_THRESHOLD:.0%} at page index={page_index} "
            f"({failures}/{len(raw_properties)} records failed). "
            "Rightmove may have changed their JSON structure."
        )
    if failures:
        log.warning(
            f"Page index={page_index}: {failures}/{len(raw_properties)} records "
            "failed to parse but below threshold — continuing."
        )

    return properties, prices


def scrape_rightmove() -> tuple[list[dict], list[dict]]:
    """
    Scrape all pages of Rightmove 2-bed SW London rentals.
    Returns (properties, prices) as lists of dicts.
    Postcodes are not included here — added separately via reverse geocoding.
    """
    session = requests.Session()
    scraped_at = str(date.today())
    all_properties, all_prices = [], []

    log.info("Fetching page 1...")
    data = _fetch_next_data(session, 0)
    search_results = _get_search_results(data)

    pagination = search_results.get("pagination", {})
    total_pages = int(pagination.get("total", 1))
    log.info(f"Found {total_pages} pages.")

    props, prices = _parse_page(search_results, scraped_at, page_index=0)
    all_properties.extend(props)
    all_prices.extend(prices)

    # Drive pagination from the options list — no hardcoded increment.
    page_indices = [
        int(opt["value"])
        for opt in pagination.get("options", [])
        if int(opt["value"]) > 0
    ]

    for i, index in enumerate(page_indices, start=2):
        time.sleep(1)  # polite delay
        log.info(f"Fetching page {i} of {total_pages} (index={index})...")
        data = _fetch_next_data(session, index)
        search_results = _get_search_results(data)
        props, prices = _parse_page(search_results, scraped_at, page_index=index)
        all_properties.extend(props)
        all_prices.extend(prices)

    log.info(f"Scraped {len(all_properties)} properties across {total_pages} pages.")
    return all_properties, all_prices


# ---------------------------------------------------------------------------
# Reverse geocoding
# ---------------------------------------------------------------------------

def reverse_geocode(lat: float, lng: float, api_key: str) -> str | None:
    """
    Reverse geocode coordinates to a postcode using the Google Maps API.
    More accurate than forward geocoding from an address string since the
    coordinates come directly from Rightmove.
    Returns the postcode string or None if not found.
    """
    r = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"latlng": f"{lat},{lng}", "key": api_key},
        timeout=10,
    )
    r.raise_for_status()

    for result in r.json().get("results", []):
        for component in result.get("address_components", []):
            if "postal_code" in component.get("types", []):
                return component["long_name"]
    return None


def add_postcodes(properties: list[dict], api_key: str) -> list[dict]:
    """
    Add postcode to each property record via reverse geocoding.
    Missing postcodes are stored as None — the bronze DLT expectation
    @dlt.expect("postcode_coverage", "postcode IS NOT NULL") will surface
    the overall null rate in the pipeline quality metrics.
    """
    missing = 0
    for prop in properties:
        postcode = reverse_geocode(prop["latitude"], prop["longitude"], api_key)
        prop["postcode"] = postcode
        if not postcode:
            missing += 1

    if missing:
        log.warning(
            f"{missing}/{len(properties)} properties have no postcode. "
            "These will surface in DLT bronze quality metrics."
        )
    return properties


if __name__ == "__main__":
    # Local smoke test — no API key or S3 needed
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    properties, prices = scrape_rightmove()
    print(f"\nProperties scraped: {len(properties)}")
    print(f"Price records:      {len(prices)}")
    print(f"\nSample property:  {properties[0]}")
    print(f"Sample price:     {prices[0]}")
