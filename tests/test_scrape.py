import pytest

from scrape import _parse_page, PARSE_FAILURE_THRESHOLD


def _make_prop(prop_id=1, price=2000, address="1 Test St", lat=51.5, lng=-0.1):
    return {
        "id": str(prop_id),
        "price": {"amount": price},
        "displayAddress": address,
        "location": {"latitude": lat, "longitude": lng},
    }


SCRAPED_AT = "2024-01-01"


def test_happy_path():
    results = {"properties": [_make_prop(1, 2000), _make_prop(2, 2500)]}
    properties, prices = _parse_page(results, SCRAPED_AT, page_index=0)

    assert len(properties) == 2
    assert len(prices) == 2

    assert properties[0] == {
        "prop_id": 1,
        "address": "1 Test St",
        "latitude": 51.5,
        "longitude": -0.1,
        "scraped_at": SCRAPED_AT,
    }
    assert prices[0] == {
        "prop_id": 1,
        "date": SCRAPED_AT,
        "price": 2000,
        "scraped_at": SCRAPED_AT,
    }


def test_empty_properties_raises():
    with pytest.raises(RuntimeError, match="No properties found"):
        _parse_page({"properties": []}, SCRAPED_AT, page_index=0)


def test_missing_properties_key_raises():
    with pytest.raises(RuntimeError, match="No properties found"):
        _parse_page({}, SCRAPED_AT, page_index=0)


def test_single_failure_below_threshold():
    bad_prop = {"id": "99"}  # missing price, address, location
    results = {"properties": [_make_prop(1), bad_prop] + [_make_prop(i) for i in range(2, 20)]}
    properties, prices = _parse_page(results, SCRAPED_AT, page_index=0)

    assert len(properties) == len(results["properties"]) - 1


def test_failure_rate_exceeds_threshold_raises():
    # All properties malformed — 100% failure rate
    total = 10
    bad_props = [{"id": str(i)} for i in range(total)]
    with pytest.raises(RuntimeError, match="Parse failure rate"):
        _parse_page({"properties": bad_props}, SCRAPED_AT, page_index=0)


def test_failure_rate_just_above_threshold_raises():
    total = 100
    n_bad = int(total * PARSE_FAILURE_THRESHOLD) + 1
    good = [_make_prop(i) for i in range(total - n_bad)]
    bad = [{"id": str(i)} for i in range(n_bad)]
    with pytest.raises(RuntimeError, match="Parse failure rate"):
        _parse_page({"properties": good + bad}, SCRAPED_AT, page_index=0)


def test_failure_rate_at_threshold_passes():
    # Exactly at threshold — should not raise (threshold is strictly greater than)
    total = 100
    n_bad = int(total * PARSE_FAILURE_THRESHOLD)
    good = [_make_prop(i) for i in range(total - n_bad)]
    bad = [{"id": str(i)} for i in range(n_bad)]
    properties, _ = _parse_page({"properties": good + bad}, SCRAPED_AT, page_index=0)
    assert len(properties) == total - n_bad
