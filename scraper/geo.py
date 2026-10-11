"""Street address -> lat/lon via the free US Census geocoder (no key), for sources without coordinates."""
import re

from . import http

URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(address):
    if not re.match(r"\s*\d+\s+\w", address or ""):
        return None
    a = re.sub(r"\s*(#|apt\.?|unit|suite)\s*[\w-]+", "", address, flags=re.I)  # unit numbers confuse the matcher
    if "san francisco" not in a.lower():
        a += ", San Francisco, CA"
    try:
        m = http.get(URL, params={"address": a, "benchmark": "Public_AR_Current", "format": "json"}).json()
        c = m["result"]["addressMatches"][0]["coordinates"]
        return c["y"], c["x"]
    except Exception:
        return None
