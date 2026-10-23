"""Parsers for agency sites, on trimmed copies of their real markup (2026-10-24)."""
import json

from scraper.adapters import buildium, jwavro, rentalsinc

BUILDIUM_CARD = """<a class="featured-listing accent-color-border-on-hover" href="/Resident/public/rentals/91717"
    target="_self" data-bedrooms="2" data-bathrooms="2" data-rent="6950.00" data-square-feet="1358"
   data-type="CondoTownhome" data-location="San Francisco,CA|94107">
    <img src="/Resident/api/public/files/download?fileName=ff7c.jpg&amp;isPreview=true" class="featured-listing__image" />
    <h3 class="featured-listing__title">2002 3rd Street, #208</h3>
    <p class="featured-listing__address">San Francisco, CA 94107</p>
    <p class="featured-listing__description hide--mobile">Bright loft in Dogpatch<div></div></p>
    <p class="featured-listing__availability hide--mobile">available November 13</p>
</a>
<a class="featured-listing" href="/Resident/public/rentals/27351" data-bedrooms="1" data-rent="2900.00"
   data-location="South San Francisco,CA|94080"><h3 class="featured-listing__title">1 Appian Way</h3></a>"""


def test_buildium_cards():
    [l] = buildium._parse(BUILDIUM_CARD, "mavericks")   # South San Francisco is dropped
    assert (l.id, l.price, l.beds, l.baths, l.sqft) == ("buildium:mavericks:91717", 6950, 2, 2.0, 1358)
    assert l.address == "2002 3rd Street, #208, San Francisco, CA 94107"
    assert l.url == "https://mavericks.managebuilding.com/Resident/public/rentals/91717"


JWAVRO_GRID = """<div class="rental-detail-label">Laundry</div>
                 <div class="rental-detail-value">In Building</div>
                 <div class="rental-detail-label">Lease Term</div>
                 <div class="rental-detail-value">1 Year</div>"""


def test_jwavro_details_grid():
    assert jwavro._details_grid(JWAVRO_GRID) == {"laundry": "In Building", "lease term": "1 Year"}


def test_rentalsinc_units():
    unit = {"id": "2fa104a02b", "slug": "418-ellis-st-510-san-francisco-2fa104a02b", "address": "418 Ellis St",
            "unit": "510", "city": "San Francisco", "price": 1695, "beds": 0, "lat": 37.78499, "lng": -122.41313}
    compact = json.dumps(unit, separators=(",", ":"))   # the real payload has no spaces
    chunk = json.dumps(f'1:["$","div",null,{{"listings":[{compact},{compact}]}}]')[1:-1]
    html = f'<script>self.__next_f.push([1,"{chunk}"])</script>'
    assert rentalsinc._units(rentalsinc._payload(html)) == [unit]
