"""Blueground: furnished-only. Neighborhood pages embed window.__INITIAL_STATE__; prices and
per-unit amenities are only on unit pages (amenities.apartment = present, struckthroughApartment = absent)."""
import json
import re

from .. import http
from ..model import Listing

BASE = "https://www.theblueground.com"
CITY = "/furnished-apartments-san-francisco-bay-area-usa"


def _state(html):
    m = re.search(r"window\.__INITIAL_STATE__=", html)
    if not m:
        return {}
    obj, _ = json.JSONDecoder().raw_decode(html, m.end())
    return obj


def _slugs(state, crit):
    wanted = [n for h in crit["neighborhoods"].values() for n in h["names"]]
    out = []

    def walk(locs):
        for loc in locs:
            name = loc.get("name", "")
            if loc.get("propertyCount") and any(re.search(rf"\b{w}\b", name, re.I) for w in wanted):
                out.append(loc["slug"])
            walk(loc.get("locations", []))

    walk(state.get("properties", {}).get("meta", {}).get("config", {}).get("locations", []))
    return sorted(set(out))


def search(cfg, crit):
    city = _state(http.get(BASE + CITY).text)
    results = {}
    for slug in _slugs(city, crit):
        props, page = [], 1
        while True:   # 18 units per page; ?page=N (N >= 2) returns the next slice
            http.pause(1)
            st = _state(http.get(f"{BASE}{CITY}/s/{slug}" + (f"?page={page}" if page > 1 else "")).text)
            batch = st.get("properties", {}).get("allProperties", {}).get("main", [])
            props += batch
            total = st.get("properties", {}).get("meta", {}).get("totalItems", 0)
            if not batch or len(props) >= total or page >= 15:
                break
            page += 1
        for p in props:
            if p.get("bedrooms") not in crit["bedrooms"]:
                continue
            a = p.get("address", {})
            dur = (p.get("rent") or {}).get("minDuration") or {}
            results[p["id"]] = Listing(
                id=f"blueground:{p['id']}",
                source="Blueground",
                url=f"{BASE}/{p['path']}",
                title=p.get("name", ""),
                beds=p.get("bedrooms"),
                baths=p.get("bathrooms"),
                sqft=p.get("lotSize"),
                address=p.get("name", ""),
                hood_text=a.get("level2", ""),
                lat=a.get("lat"),
                lon=a.get("lng"),
                photo=(p.get("photos") or [{}])[0].get("url", ""),
                available=p.get("availableFrom", ""),
                furnished=True,
                lease=f"{dur['months']}mo min" if dur.get("months") else "",
            )
    return list(results.values())


def details(l):
    html = http.get(l.url).text
    m = re.search(r'"lowestRent":\{"amount":(\d+)', html)
    l.price = int(m.group(1)) if m else None
    am = re.search(r'"amenities":\{"apartment":', html)
    if am:
        amen, _ = json.JSONDecoder().raw_decode(html, am.start() + len('"amenities":'))
        present = {x["key"] for x in amen.get("apartment", [])} | {x["key"] for x in amen.get("building", [])}
        l.in_unit_wd = "laundryRoomUnit" in present
        l.amenities = sorted(k for k in present if k in ("balcony", "rooftop", "parkingSpace", "gym", "terrace"))
        l.amenities = [("parking" if k == "parkingSpace" else k) for k in l.amenities]
    d = re.search(r'"description":"(.*?)(?<!\\)"', html)
    l.text = d.group(1).encode().decode("unicode_escape", "ignore")[:3000] if d else ""
    return l
