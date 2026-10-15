"""Decide whether a listing matches the search: "match", "maybe" (something unknown) or "reject"."""
import re
from pathlib import Path

import yaml

CRITERIA = yaml.safe_load((Path(__file__).parent.parent / "criteria.yaml").read_text())

CHECK_LABELS = {"in-unit W/D": "W/D not confirmed", "neighborhood": "Location not confirmed",
                "price": "Price/beds missing", "beds": "Price/beds missing", "furnished": "Furnishing not confirmed"}

ZIP_RE = re.compile(r"\b(94\d{3})\b")
N_MONTH_RE = re.compile(r"\b(\d{1,2})[- ]?(?:month|mo)\b", re.I)


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
    if listing.lat is not None and listing.lon is not None:
        if excluded(listing, crit):
            return None, True
        for name, h in hoods.items():
            if _inside(listing.lat, listing.lon, h):
                return name, True
        return None, True
    labeled = " ".join([listing.hood_text, listing.title, listing.address])
    for name, h in hoods.items():
        if _named(labeled, h):
            return name, not h.get("weak")
    for name, h in hoods.items():
        if _named(listing.text, h):
            return name, False   # only mentioned in the description ("walk to North Beach")
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
