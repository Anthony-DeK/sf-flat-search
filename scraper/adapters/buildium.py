"""Buildium-hosted landlord listing pages (<sub>.managebuilding.com/Resident/public/rentals). One adapter, many
landlords. Cards carry beds/baths/rent/zip as data- attributes; the unit page lists "Rental Features"."""
import re

from .. import http
from ..model import Listing, clean_text


def _parse(html, sub):
    out = []
    for m in re.finditer(r'<a class="featured-listing[^"]*" href="(/Resident/public/rentals/(\d+))"(.*?)</a>', html, re.S):
        path, uid, card = m.groups()
        attr = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', card))
        if not attr.get("location", "").lower().startswith("san francisco,"):   # "South San Francisco,CA|94080" too
            continue
        title = re.search(r'featured-listing__title">(.*?)</h3>', card, re.S)
        addr2 = re.search(r'featured-listing__address">(.*?)</p>', card, re.S)
        desc = re.search(r'featured-listing__description[^>]*>(.*?)<div', card, re.S)
        avail = re.search(r'featured-listing__availability[^>]*>(.*?)</p>', card, re.S)
        img = re.search(r'<img src="([^"]+)"', card)
        street = clean_text(title.group(1)) if title else ""
        rent = attr.get("rent", "")
        out.append(Listing(
            id=f"buildium:{sub}:{uid}",
            source=f"Buildium · {sub}",
            url=f"https://{sub}.managebuilding.com{path}",
            title=street,
            price=int(float(rent)) if rent else None,
            beds=int(attr["bedrooms"]) if attr.get("bedrooms", "").isdigit() else None,
            baths=float(attr["bathrooms"]) if re.fullmatch(r"[\d.]+", attr.get("bathrooms", "")) else None,
            sqft=int(attr["square-feet"]) if attr.get("square-feet", "").isdigit() else None,
            address=f"{street}, {clean_text(addr2.group(1))}" if addr2 else street,
            text=clean_text(desc.group(1)) if desc else "",
            photo=f"https://{sub}.managebuilding.com{img.group(1)}".replace("&amp;", "&") if img else "",
            available=clean_text(avail.group(1)) if avail else "",
        ))
    return out


def search(cfg, crit):
    results = []
    for sub in cfg["subdomains"]:
        http.pause(1)
        try:
            results += _parse(http.get(f"https://{sub}.managebuilding.com/Resident/public/rentals").text, sub)
        except Exception as e:  # one dead landlord page shouldn't sink the rest
            print(f"  buildium {sub}: {e}")
    return results


def details(l):
    html = http.get(l.url).text
    desc = re.search(r'unit-detail__description">(.*?)</(?:p|div)>', html, re.S)
    # First features list is the unit's ("Rental Features"); the second is the building's.
    lists = re.findall(r'<ul class="unit-detail__features-list">(.*?)</ul>', html, re.S)
    unit = [clean_text(i) for i in re.findall(r"<li[^>]*>(.*?)</li>", lists[0], re.S)] if lists else []
    bldg = [clean_text(i) for i in re.findall(r"<li[^>]*>(.*?)</li>", lists[1], re.S)] if len(lists) > 1 else []
    l.text = "\n".join([clean_text(desc.group(1)) if desc else l.text,
                        "Features: " + " | ".join(unit), "Building: " + " | ".join(bldg)])
    low = {i.lower() for i in unit}
    if {"washer", "dryer"} <= low or low & {"washer/dryer", "washer & dryer", "in unit laundry", "in-unit laundry"}:
        l.in_unit_wd = True
    if "furnished" in low:
        l.furnished = True
    return l


def still_listed(rec):
    """A taken-down unit's page redirects back to the rentals index."""
    r = http.get_any(rec["url"])
    if r.status_code in (404, 410) or (r.ok and not re.search(r"/rentals/\d+$", r.url)):
        return False
    return True if r.ok else None
