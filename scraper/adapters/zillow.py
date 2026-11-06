"""Zillow results saved to the repo by a Claude agent using the claude.ai Zillow connector (Zillow blocks
scrapers, and the connector can only be called by Claude, not by this job).

data/zillow/all.json        raw connector output: SF areas, 1-2BR, rent range, in-unit laundry
data/zillow/furnished.json  same search plus Zillow's "furnished" filter (only used to tag furnishing)
data/zillow/meta.json       {"fetched_at": ISO time}; stale results raise so the health check flags the agent
Results are either single units ("property") or buildings with several matching units ("group")."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..model import Listing

ROOT = Path(__file__).parent.parent.parent


def _load(path):
    return json.loads(path.read_text())["results"] if path.exists() else []


def _num(v, pick=min):
    """Ranges on buildings sometimes carry only one end."""
    if not isinstance(v, dict):
        return v
    ends = [e for e in (v.get("min"), v.get("max")) if e is not None]
    return pick(ends) if ends else None


def _zpid(url):
    m = re.search(r"/(\d+)_zpid", url or "")
    return m.group(1) if m else None


def _street(addr):
    return re.sub(r"\s+", " ", (addr or "").lower().split("#")[0]).strip()


def search(cfg, crit):
    folder = ROOT / cfg.get("dir", "data/zillow")
    meta = json.loads((folder / "meta.json").read_text()) if (folder / "meta.json").exists() else {}
    if not meta.get("fetched_at"):
        return []
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(meta["fetched_at"])).days
    if age > cfg.get("max_age_days", 2):
        raise RuntimeError(f"Zillow results are {age} days old; the daily Claude search isn't running")

    furnished = _load(folder / "furnished.json")
    furn_ids = {_zpid(r["result"].get("homeDetailsPageUrl")) for r in furnished}
    furn_streets = {_street((r["result"].get("summary") or r["result"])["formattedAddress"]["line1"]) for r in furnished}

    out = {}
    for r in _load(folder / "all.json") + furnished:
        x = r["result"]
        group = r["type"] == "group"
        s = x["summary"] if group else x
        url = (x.get("homeDetailsPageUrl") or "").split("?")[0]
        zpid = _zpid(url)
        addr = s["formattedAddress"]
        ll = s.get("geoRegion", {}).get("latLong", {})
        beds = s.get("bedroomCount")
        lo, hi = _num(beds), _num(beds, max)
        beds_ok = [b for b in crit["bedrooms"] if isinstance(beds, dict) and lo is not None and lo <= b <= hi]
        price = s.get("price", {}).get("filteredPrice")
        title = s.get("title") or addr["line1"]
        if group:
            n = x.get("groupingInfo", {}).get("matchingPropertyCount")
            if _num(price) is not None:
                title = f"{title}: {n} matching units, ${_num(price):,}–${_num(price, max):,}"
        out.setdefault(zpid or url, Listing(
            id=f"zillow:{zpid or url}",
            source="Zillow (via Claude)",
            url=url,
            title=title,
            price=_num(price),
            beds=beds_ok[0] if beds_ok else _num(beds),
            baths=_num(s.get("bathroomCount")),
            sqft=_num(s.get("livingAreaSquareFeet")),
            address=f"{addr['line1']}, San Francisco, CA {addr.get('postalCode', '')}".strip(),
            lat=ll.get("latitude"), lon=ll.get("longitude"),
            in_unit_wd=True,   # searched with Zillow's in-unit laundry filter
            # Only the furnished search can say "furnished"; absence there doesn't prove unfurnished.
            furnished=True if (zpid in furn_ids or _street(addr["line1"]) in furn_streets) else None,
        ))
    return list(out.values())


def details(l):
    return l   # Zillow pages block scrapers; the connector result is all we have
