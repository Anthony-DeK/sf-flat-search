"""AppFolio-hosted landlord listing pages (<sub>.appfolio.com/listings). One adapter, many landlords."""
import re

from .. import http
from ..model import Listing, clean_text, parse_price


def _field(block, label):
    m = re.search(rf'<dt class="detail-box__label">\s*{label}\s*</dt>\s*<dd class="detail-box__value">(.*?)</dd>',
                  block, re.S | re.I)
    return clean_text(m.group(1)) if m else ""


def _parse(html, sub):
    out = []
    for block in re.split(r'<div class="listing-item result', html)[1:]:
        addr = re.search(r'js-listing-address">(.*?)</span>', block, re.S)
        address = clean_text(addr.group(1)) if addr else ""
        if "San Francisco" not in address:
            continue
        link = re.search(r'href="(/listings/detail/[^"]+)"', block)
        title = re.search(r'listing-item__title[^>]*>(.*?)</', block, re.S)
        bb = _field(block, "Bed / Bath")
        beds = re.search(r"(\d+)\s*bd", bb)
        baths = re.search(r"([\d.]+)\s*ba", bb)
        sqft = re.search(r"([\d,]+)", _field(block, "Square Feet"))
        desc = re.search(r'js-listing-description">(.*?)</p>', block, re.S)
        img = re.search(r'data-original="([^"]+)"', block)
        out.append(Listing(
            id=f"appfolio:{sub}:{link.group(1).rsplit('/', 1)[-1] if link else address}",
            source=f"AppFolio · {sub}",
            url=f"https://{sub}.appfolio.com{link.group(1)}" if link else f"https://{sub}.appfolio.com/listings",
            title=clean_text(title.group(1)) if title else address,
            price=parse_price(_field(block, "RENT")) or None,
            beds=(0 if "studio" in bb.lower() else int(beds.group(1))) if (beds or "studio" in bb.lower()) else None,
            baths=float(baths.group(1)) if baths else None,
            sqft=int(sqft.group(1).replace(",", "")) if sqft else None,
            address=address,
            text=clean_text(desc.group(1)) if desc else "",
            photo=img.group(1) if img else "",
            available=_field(block, "Available"),
        ))
    return out


def search(cfg, crit):
    results = []
    for sub in cfg["subdomains"]:
        http.pause(1)
        try:
            results += _parse(http.get(f"https://{sub}.appfolio.com/listings").text, sub)
        except Exception as e:  # one dead landlord page shouldn't sink the rest
            print(f"  appfolio {sub}: {e}")
    return results


def details(l):
    html = http.get(l.url).text
    paras = [clean_text(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S)]
    items = [clean_text(i) for i in re.findall(r'<li class="list__item">(.*?)</li>', html, re.S)]
    l.text = "\n".join([max(paras, key=len, default=""), "Features: " + " | ".join(items)])
    # Amenity/appliance bullets are structured enough to trust over free text.
    low = [i.lower() for i in items]
    if any(i in ("washer/dryer", "washer & dryer", "washer and dryer") or "in unit" in i and ("laundry" in i or "washer" in i)
           for i in low):
        l.in_unit_wd = True
    if any(i in ("furnished", "fully furnished") for i in low):
        l.furnished = True
    return l
