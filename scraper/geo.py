"""Street address -> lat/lon via the free US Census geocoder (no key), for sources without coordinates.
Returns None when the address has no match; raises on network errors so the caller can retry later."""
import re

from . import http

URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(address):
    if not re.match(r"\s*\d+[A-Za-z]?\s+\w", address or ""):
        return None
    a = re.sub(r"\s*(#|apt\.?|unit|suite)\s*[\w-]+", "", address, flags=re.I)  # unit numbers confuse the matcher
    a = re.sub(r"^\s*(\d+)(?:[A-Za-z]|\s[A-Z](?=\s+[A-Z]))\b", r"\1", a)       # 571A Minna, 316 B Maple -> no letter
    if "san francisco" not in a.lower():
        a += ", San Francisco, CA"
    m = http.get(URL, params={"address": a, "benchmark": "Public_AR_Current", "format": "json"}).json()
    matches = m["result"]["addressMatches"]
    return (matches[0]["coordinates"]["y"], matches[0]["coordinates"]["x"]) if matches else None
