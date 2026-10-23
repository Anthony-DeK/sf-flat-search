"""Decide whether a listing matches the search: "match", "maybe" (something unknown) or "reject"."""
import math
import re
from pathlib import Path

import yaml

CRITERIA = yaml.safe_load((Path(__file__).parent.parent / "criteria.yaml").read_text())

CHECK_LABELS = {"in-unit W/D": "W/D not confirmed", "neighborhood": "Location not confirmed",
                "price": "Price/beds missing", "beds": "Price/beds missing", "furnished": "Furnishing not confirmed"}

ZIP_RE = re.compile(r"\b(94\d{3})\b")
N_MONTH_RE = re.compile(r"\b(\d{1,2})[- ]?(?:month|mo)\b", re.I)
# Pins and geocodes can land a block off; a point this close to a neighborhood the listing names counts as in it.
NEAR_EDGE_M = 250
# "walk to North Beach", "easy commute to Financial, SOMA": the description names a place nearby, not the location.
NEARBY_RE = re.compile(r"\b(near(by)?|close to|walk(ing|able)?|steps|blocks?|minutes?|mins?|commute|access|"
                       r"border(s|ing)?|between|views? of)\b\W+(?:\w+\W+){0,3}$", re.I)
STREET_AFTER_RE = re.compile(r"\s+(st|street|ave|avenue|blvd)\b", re.I)   # "Castro Street", "Hayes St"


def _flag(structured, text, rule):
    """Structured value from the source wins; otherwise fall back to keyword regexes."""
    if structured is not None:
        return structured
    order = ("match", "reject") if rule.get("match_first") else ("reject", "match")
    for key in order:
        if re.search(rule[key], text, re.I):
            return key == "match"
    return None


def _named(text, h):
    return any(re.search(rf"\b{n}\b", text, re.I) for n in h["names"])


def _mentioned(text, h, nearby_ok=False):
    """Description mentions of the area, never "X Street". Unless nearby_ok, also skip "near X" / "commute to X"."""
    for n in h["names"]:
        for m in re.finditer(rf"\b{n}\b", text, re.I):
            if STREET_AFTER_RE.match(text, m.end()):
                continue
            if nearby_ok or not NEARBY_RE.search(text[max(0, m.start() - 40):m.start()]):
                return True
    return False


def _dist_m(lat, lon, h):
    """Meters from the point to the area's outline (0 inside); infinite for areas with no shape."""
    if "box" not in h and "poly" not in h:
        return math.inf
    if _inside(lat, lon, h):
        return 0
    if "box" in h:
        la0, la1, lo0, lo1 = h["box"]
        pts = [[la0, lo0], [la0, lo1], [la1, lo1], [la1, lo0]]
    else:
        pts = h["poly"]
    kx = 111320 * math.cos(math.radians(lat))   # local flat projection; fine at neighborhood scale
    best = math.inf
    for (y1, x1), (y2, x2) in zip(pts, pts[1:] + pts[:1]):
        ax, ay, bx, by = (x1 - lon) * kx, (y1 - lat) * 110540, (x2 - lon) * kx, (y2 - lat) * 110540
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def _inside(lat, lon, h):
    if "box" not in h and "poly" not in h:
        return False
    if "box" in h:
        la0, la1, lo0, lo1 = h["box"]
        return la0 <= lat <= la1 and lo0 <= lon <= lo1
    # Ray casting point-in-polygon.
    pts, inside = h["poly"], False
    for (y1, x1), (y2, x2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def excluded(listing, crit=CRITERIA):
    if listing.lat is None:
        return None
    return next((name for name, h in (crit.get("exclude") or {}).items()
                 if _inside(listing.lat, listing.lon, h)), None)


def neighborhood(listing, crit=CRITERIA):
    """Return (name, confident). name is None when the listing is outside the target area."""
    hoods = crit["neighborhoods"]
    labeled = " ".join([listing.hood_text, listing.title, listing.address])
    if listing.lat is not None and listing.lon is not None:
        if excluded(listing, crit):
            return None, True
        for name, h in hoods.items():
            if _inside(listing.lat, listing.lon, h):
                return name, True
        # Beyond that, the point wins: posters label Ocean Beach "lower nob hill".
        for name, h in hoods.items():
            if _named(labeled, h) and _dist_m(listing.lat, listing.lon, h) <= NEAR_EDGE_M:
                return name, True
        return None, True
    for name, h in hoods.items():
        if _named(labeled, h):
            return name, not h.get("weak")
    # Only in the description: "located in Nob Hill" first, then "walk to North Beach" as a last hint.
    for nearby_ok in (False, True):
        for name, h in hoods.items():
            if _mentioned(listing.text, h, nearby_ok):
                return name, False
    m = ZIP_RE.search(listing.address or "")
    if m and m.group(1) in crit["weak_zips"]:
        return f"zip {m.group(1)}", False
    return None, False


def lease_term(listing, crit=CRITERIA):
    if listing.lease:
        return listing.lease
    t = f"{listing.title}\n{listing.text}"
    for term, pat in crit["lease"].items():
        if re.search(pat, t, re.I):
            return term
    m = N_MONTH_RE.search(t)
    return f"{m.group(1)}mo" if m else ""


def evaluate(listing, crit=CRITERIA):
    text = f"{listing.title}\n{listing.text}"
    reasons, unknown = [], []
    if re.search(crit["not_residential"], listing.title, re.I):
        reasons.append("not residential")

    p = crit["price"]
    if listing.price is None:
        unknown.append("price")
    elif not p["min"] <= listing.price <= p["max"]:
        reasons.append(f"price ${listing.price}")

    if listing.beds is None:
        unknown.append("beds")
    elif listing.beds not in crit["bedrooms"]:
        reasons.append(f"{listing.beds} beds")

    hood, confident = neighborhood(listing, crit)
    if excl := excluded(listing, crit):
        reasons.append(f"excluded area: {excl}")
    elif hood is None:
        reasons.append("outside target neighborhoods")
    elif not confident:
        unknown.append("neighborhood")

    furnished = _flag(listing.furnished, text, crit["furnishing"])
    wd = _flag(listing.in_unit_wd, text, crit["required"]["in_unit_wd"])
    checks = [("in-unit W/D", wd)]
    if crit["furnishing"].get("require_furnished"):
        checks.append(("furnished", furnished))
    for label, val in checks:
        if val is False:
            reasons.append(f"no {label}")
        elif val is None:
            unknown.append(label)

    bonus = sorted({re.sub(r"[?\\]", "", b) for b in crit["bonus"] if re.search(rf"\b{b}\b", text, re.I)}
                   | {a for a in listing.amenities if a in ("balcony", "rooftop", "parking", "gym", "terrace")})

    status = "reject" if reasons else ("maybe" if unknown else "match")
    return {
        "status": status,
        # What a "maybe" still needs, in plain words, for the email and dashboard.
        "check": sorted({CHECK_LABELS[u] for u in unknown if u in CHECK_LABELS}),
        "hood": hood,
        "reasons": reasons,
        "unknown": unknown,
        "furnished": furnished,
        "in_unit_wd": wd,
        "lease": lease_term(listing, crit),
        "bonus": bonus,
    }
