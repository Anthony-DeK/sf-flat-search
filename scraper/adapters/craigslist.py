"""Craigslist via the JSON endpoint its own search page uses (sapi.craigslist.org).

Items are compact arrays: [id_offset, posted_offset, ?, price, "loc:hood:desc~lat~lon", <tagged lists>..., title]
Tagged lists: [5, beds, sqft], [6, slug], [10, "$price"], [4, images...].
"""
import re

from .. import http
from ..model import Listing, clean_text

API = "https://sapi.craigslist.org/web/v8/postings/search/full"


def _parse(data, cat):
    dec = data["decode"]
    out = []
    for it in data["items"]:
        loc = next((x for x in it if isinstance(x, str) and "~" in x), "")
        idx, lat, lon = (loc.split("~") + [None, None])[:3]
        li = [int(i) for i in idx.split(":")] if idx else []
        locations = dec.get("locations", [])
        entry = locations[li[0]] if li and li[0] < len(locations) else None
        # Entries look like [1, "sfbay", "sfc"]; some (area-wide posts) have no subarea.
        subarea = entry[2] if isinstance(entry, list) and len(entry) > 2 else ""
        if subarea != "sfc":
            continue
        tags = {x[0]: x[1:] for x in it if isinstance(x, list) and x and isinstance(x[0], int)}
        hood_names = dec.get("locationDescriptions") or dec.get("neighborhoods") or []
        hood = hood_names[li[2]] if len(li) > 2 and li[2] < len(hood_names) else ""
        pid = dec["minPostingId"] + it[0]
        slug = tags.get(6, ["x"])[0]
        beds = tags.get(5, [None, None])
        out.append(Listing(
            id=f"craigslist:{pid}",
            source=f"Craigslist ({cat})",
            url=f"https://sfbay.craigslist.org/sfc/{cat}/d/{slug}/{pid}.html",
            title=[x for x in it if isinstance(x, str) and "~" not in x][-1],
            price=it[3] if isinstance(it[3], int) else None,
            beds=beds[0] if beds else None,
            sqft=(beds[1] or None) if len(beds) > 1 else None,
            hood_text=hood,
            lat=float(lat) if lat else None,
            lon=float(lon) if lon else None,
        ))
    return out


def search(cfg, crit):
    results = {}
    for q in cfg["queries"]:
        params = {"batch": "1-0-360-0-0", "cc": "US", "lang": "en", "area_id": 1,
                  "searchPath": cfg["category"],
                  "min_price": crit["price"]["min"], "max_price": crit["price"]["max"], **q}
        data = http.get(API, params=params).json()["data"]
        for l in _parse(data, cfg["category"]):
            # A listing matched by the is_furnished filter is structurally furnished.
            if q.get("is_furnished"):
                l.furnished = True
            if q.get("laundry") == 1:
                l.in_unit_wd = True
            results.setdefault(l.id, l)
    return list(results.values())


def details(l):
    html = http.get(l.url).text
    m = re.search(r'<section id="postingbody">(.*?)</section>', html, re.S)
    l.text = clean_text(m.group(1)).replace("QR Code Link to This Post", "").strip() if m else ""
    # The attribute sidebar ("1BR / 1Ba", "w/d in unit", "furnished", ...) sits between the first attrgroup and the body.
    start = html.find('class="attrgroup"')
    end = html.find('id="postingbody"')
    attrs = clean_text(html[start:end]) if 0 <= start < end else ""
    attrs_l = attrs.lower()
    if "w/d in unit" in attrs_l:
        l.in_unit_wd = True
    elif re.search(r"laundry (on site|in bldg)|no laundry|w/d hookups", attrs_l):
        l.in_unit_wd = l.in_unit_wd if l.in_unit_wd else False
    if re.search(r"\bfurnished\b", attrs_l):
        l.furnished = True
    img = re.search(r'<img[^>]+src="(https://images\.craigslist\.org/[^"]+)"', html)
    l.photo = img.group(1) if img else ""
    addr = re.search(r'<h2 class="street-address">(.*?)</h2>', html, re.S)
    l.address = clean_text(addr.group(1)) if addr else ""
    av = re.search(r"available[^<]{0,40}", attrs, re.I)
    l.available = av.group(0).strip() if av else ""
    return l
