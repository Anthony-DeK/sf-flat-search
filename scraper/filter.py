"""Decide whether a listing matches the search: "match", "maybe" (something unknown) or "reject"."""
import re
from pathlib import Path

import yaml

CRITERIA = yaml.safe_load((Path(__file__).parent.parent / "criteria.yaml").read_text())

ZIP_RE = re.compile(r"\b(94\d{3})\b")
N_MONTH_RE = re.compile(r"\b(\d{1,2})[- ]?(?:month|mo)\b", re.I)


def _flag(structured, text, rule):
    """Structured value from the source wins; otherwise fall back to keyword regexes."""
    if structured is not None:
        return structured
    if re.search(rule["reject"], text, re.I):
        return False
    if re.search(rule["match"], text, re.I):
        return True
    return None


def neighborhood(listing, crit=CRITERIA):
    """Return (name, confident). name is None when the listing is outside the target area."""
    hoods = crit["neighborhoods"]
    if listing.lat is not None and listing.lon is not None:
        for name, h in hoods.items():
            la0, la1, lo0, lo1 = h["box"]
            if la0 <= listing.lat <= la1 and lo0 <= listing.lon <= lo1:
                return name, True
        return None, True
    labeled = " ".join([listing.hood_text, listing.title, listing.address]).lower()
    for name, h in hoods.items():
        if any(n in labeled for n in h["names"]):
            return name, True
    body = listing.text.lower()
    for name, h in hoods.items():
        if any(n in body for n in h["names"]):
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
    if hood is None:
        reasons.append("outside target neighborhoods")
    elif not confident:
        unknown.append("neighborhood")

    furnished = _flag(listing.furnished, text, crit["required"]["furnished"])
    wd = _flag(listing.in_unit_wd, text, crit["required"]["in_unit_wd"])
    for label, val in (("furnished", furnished), ("in-unit W/D", wd)):
        if val is False:
            reasons.append(f"no {label}")
        elif val is None:
            unknown.append(label)

    bonus = sorted({re.sub(r"[?\\]", "", b) for b in crit["bonus"] if re.search(rf"\b{b}\b", text, re.I)}
                   | {a for a in listing.amenities if a in ("balcony", "rooftop", "parking", "gym", "terrace")})

    status = "reject" if reasons else ("maybe" if unknown else "match")
    return {
        "status": status,
        "hood": hood,
        "reasons": reasons,
        "unknown": unknown,
        "furnished": furnished,
        "in_unit_wd": wd,
        "lease": lease_term(listing, crit),
        "bonus": bonus,
    }
