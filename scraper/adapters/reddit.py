"""r/SFBayHousing via its public Atom feed. Free-text posts, so most land in "maybe" for a human look."""
import re
import xml.etree.ElementTree as ET

from .. import http
from ..model import Listing, clean_text, parse_beds, parse_price

NS = {"a": "http://www.w3.org/2005/Atom"}
OFFER_RE = re.compile(r"\b(for rent|available|sublet|sublease|lease takeover|\$\d)", re.I)
WANTED_RE = re.compile(r"\b(looking for|seeking|iso|in search of|roommate wanted)\b", re.I)


def search(cfg, crit):
    root = ET.fromstring(http.get(cfg["url"]).content)
    out = []
    for e in root.findall("a:entry", NS):
        title = e.findtext("a:title", "", NS)
        body = clean_text(e.findtext("a:content", "", NS))
        text = f"{title}\n{body}"
        if WANTED_RE.search(title) or not OFFER_RE.search(text):
            continue
        out.append(Listing(
            id=f"reddit:{e.findtext('a:id', '', NS)}",
            source="r/SFBayHousing",
            url=e.find("a:link", NS).get("href"),
            title=title,
            price=parse_price(text),
            beds=parse_beds(text),
            text=body[:3000],
        ))
    return out


def details(l):
    return l
