"""RentSFNow (WordPress 'wpas' search over RentCafe inventory). The furnished=yes flag switches the
result set to their furnished catalog; cards show neighborhood, address, beds/baths/price."""
import re

from .. import http
from ..model import Listing, clean_text, parse_price

BASE = "https://www.rentsfnow.com"


def search(cfg, crit):
    out, page = [], 1
    while page <= 10:
        html = http.post(f"{BASE}/wp-admin/admin-ajax.php", data={
            "city": "san-francisco", "furnished": "yes", "sort": "priority_value-desc", "view": "list",
            "action": "wpas_ajax_load", "page": page, "type": "search"}).text
        cards = re.split(r'<div class="grid-x grid-margin-x apartment', html)[1:]
        for c in cards:
            pid = re.search(r'id="post-(\d+)"', c)
            href = re.search(r'href="(/apartments/rental/[^"]+)"', c)
            hood = re.search(r"<h3>(.*?)</h3>", c, re.S)
            addr = re.search(r"<h2>(.*?)</h2>", c, re.S)
            info = re.search(r'<p class="apartment-info">(.*?)</p>', c, re.S)
            info_t = clean_text(info.group(1)) if info else ""
            beds = re.search(r"(\d+)\s*Bed", info_t)
            img = re.search(r"background-image:url\('([^']+)'", c)
            out.append(Listing(
                id=f"rentsfnow:{pid.group(1) if pid else href.group(1)}",
                source="RentSFNow",
                url=BASE + href.group(1) if href else BASE,
                title=clean_text(addr.group(1)) if addr else "",
                price=parse_price(info_t),
                beds=0 if "Studio" in info_t else (int(beds.group(1)) if beds else None),
                address=(clean_text(addr.group(1)) + ", San Francisco") if addr else "",
                hood_text=clean_text(hood.group(1)) if hood else "",
                photo=img.group(1) if img else "",
                furnished=True,
            ))
        last = re.search(r'id="last_page"[^>]*value="(\d+)"|name="last_page" value="(\d+)"', html)
        last_n = int(next(g for g in last.groups() if g)) if last else 1
        if not cards or page >= last_n:
            break
        page += 1
        http.pause(1)
    return out


def details(l):
    html = http.get(l.url).text
    body = re.search(r'<div class="[^"]*(?:unit-description|apartment-description|description)[^"]*">(.*?)</div>', html, re.S)
    feats = re.findall(r"<li[^>]*>(.*?)</li>", html, re.S)
    l.text = (clean_text(body.group(1)) if body else "") + "\n" + " | ".join(
        clean_text(f) for f in feats if 3 < len(clean_text(f)) < 60)
    return l
