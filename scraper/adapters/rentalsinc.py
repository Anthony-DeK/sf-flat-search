"""Rentals Inc. (rentalsinc.com), an SF leasing agency on ShowMojo. The Next.js listings page embeds every unit
(address, price, beds, coordinates) in its React Server Components payload; unit pages add the description."""
import json
import re

from .. import http
from ..model import Listing

BASE = "https://www.rentalsinc.com"
RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)


def _payload(html):
    return "".join(json.loads(f'"{c}"') for c in RSC_RE.findall(html))


def _units(payload):
    dec, out = json.JSONDecoder(), {}
    for m in re.finditer(r'\{"id":"[0-9a-f]{10}","slug":', payload):
        obj, _ = dec.raw_decode(payload, m.start())
        out.setdefault(obj["id"], obj)
    return list(out.values())


def search(cfg, crit):
    out = []
    for u in _units(_payload(http.get(f"{BASE}/listings").text)):
        if u.get("city") != "San Francisco" or u.get("status") != "available":
            continue
        street = u["address"] + (f" #{u['unit']}" if u.get("unit") else "")
        out.append(Listing(
            id=f"rentalsinc:{u['id']}",
            source="Rentals Inc.",
            url=f"{BASE}/listings/{u['slug']}",
            title=street,
            price=u.get("price") if isinstance(u.get("price"), int) else None,
            beds=u.get("beds") if isinstance(u.get("beds"), int) else None,
            baths=u.get("baths") if isinstance(u.get("baths"), (int, float)) else None,
            sqft=u.get("sqft") if isinstance(u.get("sqft"), int) else None,
            address=f"{street}, San Francisco, CA {u.get('zip', '')}".strip(),
            lat=u.get("lat"), lon=u.get("lng"),
            photo=u.get("photo") or "",
        ))
    return out


def _strings(node):
    if isinstance(node, str):
        if node not in ("$", "$1") and not node.isdigit():
            yield node
    elif isinstance(node, list):
        for n in node:
            yield from _strings(n)
    elif isinstance(node, dict):
        yield from _strings(node.get("children"))


def details(l):
    p = _payload(http.get(l.url).text)
    key = '"className":"text-soft text-[15px] leading-relaxed","children":'   # the description block
    i = p.find(key)
    if i >= 0:
        body, _ = json.JSONDecoder().raw_decode(p, i + len(key))
        l.text = "\n".join(_strings(body))[:3000]
    return l


def still_listed(rec):
    r = http.get_any(rec["url"])
    if r.status_code in (404, 410):
        return False
    return ('"availability":"https://schema.org/InStock"' in r.text) if r.ok else None
