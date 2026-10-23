"""J. Wavro Associates (jwavro.com), an SF leasing agency. Cards carry beds/price/neighborhood as data- attributes;
unit pages add schema.org coordinates and a details grid ("Laundry: In Unit" / "In Building", "Furnished")."""
import json
import re

from .. import http
from ..model import Listing, clean_text

BASE = "https://www.jwavro.com"


def search(cfg, crit):
    html = http.get(f"{BASE}/rental_list.php", params={"hood": "San Francisco"}).text
    out = []
    for m in re.finditer(r"<a href='(/rentals/(\d+)/[^']*)' class='rental-card-link'([^>]*)>(.*?)</a>", html, re.S):
        path, uid, attrs, card = m.groups()
        a = dict(re.findall(r"data-([a-z]+)='([^']*)'", attrs))
        title = re.search(r"rental-card-description'>(.*?)</div>", card, re.S)
        img = re.search(r"<img src='([^']+)'", card)
        out.append(Listing(
            id=f"jwavro:{uid}",
            source="J. Wavro",
            url=BASE + path,
            title=clean_text(title.group(1)) if title else "",
            price=int(a["price"]) if a.get("price", "").isdigit() else None,
            beds=int(a["bedrooms"]) if a.get("bedrooms", "").isdigit() else None,
            hood_text=a.get("neighborhood", ""),
            photo=img.group(1) if img else "",
        ))
    return out


def _details_grid(html):
    return {clean_text(k).lower(): clean_text(v) for k, v in re.findall(
        r'rental-detail-label">(.*?)</div>\s*<div class="rental-detail-value[^"]*">(.*?)</div>', html, re.S)}


def details(l):
    html = http.get(l.url).text
    about = re.search(r"About This Property</h2>(.*?)<h2", html, re.S)
    grid = _details_grid(html)
    l.text = (clean_text(about.group(1)) if about else "") + "\nDetails: " + " | ".join(f"{k}: {v}" for k, v in grid.items())
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            geo = json.loads(block).get("geo") or {}
        except (ValueError, AttributeError):
            continue
        if geo.get("latitude"):
            l.lat, l.lon = float(geo["latitude"]), float(geo["longitude"])
    # Usually cross streets ("Pacific at Fillmore Street, ..."); the coordinates above are what locate the unit.
    street = re.search(r'rental-hero-subtitle">(.*?)</div>', html, re.S)
    l.address = clean_text(street.group(1)) if street else ""
    laundry = grid.get("laundry", "").lower()
    if "in unit" in laundry or "in-unit" in laundry:
        l.in_unit_wd = True
    elif laundry:
        l.in_unit_wd = False
    furn = grid.get("furnished", "").lower()
    l.furnished = True if furn.startswith(("yes", "furnished", "fully")) else False if furn.startswith(("no", "unfurnished")) else None
    if term := grid.get("lease term", ""):
        l.lease = "12mo" if "1 year" in term.lower() else "m2m" if "month" in term.lower() and "to" in term.lower() else ""
    return l


def still_listed(rec):
    r = http.get_any(rec["url"])
    if r.status_code in (404, 410) or (r.ok and f"/rentals/{rec['id'].split(':')[1]}/" not in r.url):
        return False
    return True if r.ok else None
