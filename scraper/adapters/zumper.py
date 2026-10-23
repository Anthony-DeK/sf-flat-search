"""Zumper/PadMapper (shared backend) via the JSON endpoint its web app uses. Aggregates small-landlord
feeds (ShowMojo, Hemlane, TurboTenant, ...) we can't reach directly. Furnishing comes from amenity tags."""
from .. import http
from ..model import Listing

API = "https://www.zumper.com/api/t/1/pages/listables"
LISTING_API = "https://www.zumper.com/api/t/1/listings/"
IN_UNIT_TAGS = {"In-Unit Laundry", "Washer and Dryer", "Washer/Dryer In Unit", "Washer/Dryer in Unit", "In Unit Washer & Dryer"}
BONUS_TAGS = {"Balcony": "balcony", "Private Balcony": "balcony", "Roof Deck": "rooftop", "Rooftop": "rooftop",
              "Assigned Parking": "parking", "Garage Parking": "parking", "Gym": "gym", "Fitness Center": "gym",
              "Private Patio": "terrace", "Terrace": "terrace"}


def search(cfg, crit):
    out, offset = [], 0
    skip = set(cfg.get("skip_feeds", []))
    while offset < 500:
        rows = http.post(API, json={
            "url": "san-francisco-ca", "limit": 100, "offset": offset,
            "min_price": crit["price"]["min"], "max_price": crit["price"]["max"],
            "bedrooms": crit["bedrooms"]}).json()["listables"]
        for x in rows:
            if x.get("feed_name") in skip:
                continue
            tags = set(x.get("amenity_tags") or []) | set(x.get("building_amenity_tags") or [])
            unit_tags = set(x.get("amenity_tags") or [])
            days = x.get("min_lease_days")
            out.append(Listing(
                id=f"zumper:{x['listing_id']}",
                source=f"Zumper · {x.get('brokerage_name') or x.get('feed_name') or 'listing'}",
                url="https://www.zumper.com" + (x.get("url") or f"/apartments-for-rent/{x['listing_id']}"),
                title=x.get("title") or x.get("building_name") or x.get("address", ""),
                # Multi-unit buildings report a range; the floor is what you'd actually pay.
                price=x.get("min_price"),
                beds=x.get("min_bedrooms") if x.get("min_bedrooms") in crit["bedrooms"] else x.get("max_bedrooms"),
                baths=x.get("min_bathrooms"),
                address=f"{x.get('address', '')}, San Francisco, CA {x.get('zipcode') or ''}".strip(),
                hood_text=x.get("neighborhood_name") or "",
                lat=x.get("lat"), lon=x.get("lng"),
                text=(x.get("short_description") or "") + "\nFeatures: " + " | ".join(sorted(unit_tags)),
                available=str(x.get("date_available") or ""),
                # The Furnished tag is what Zumper's own furnished filter uses; untagged and never mentioned = unfurnished.
                furnished=True if "Furnished" in unit_tags else (
                    None if "furnish" in f"{x.get('title')} {x.get('short_description')}".lower() else False),
                in_unit_wd=True if unit_tags & IN_UNIT_TAGS else None,
                lease=f"{round(days / 30)}mo min" if days and days >= 28 else "",
                amenities=sorted({v for k, v in BONUS_TAGS.items() if k in tags}),
            ))
        if len(rows) < 100:
            break
        offset += 100
        http.pause(1)
    return out


def details(l):
    return l   # listing pages sit behind a JS challenge; the API row is all we get


def still_listed(rec):
    """Pages are JS-gated, but the listing API answers; listing_status 1 is the only live state seen."""
    r = http.get_any(LISTING_API + rec["id"].split(":", 1)[1])
    if r.status_code == 404:
        return False
    return r.json().get("listing_status") == 1 if r.ok else None
