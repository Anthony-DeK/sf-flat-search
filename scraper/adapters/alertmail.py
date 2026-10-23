"""Saved-search alert emails from sites that block scrapers (Furnished Finder, Zillow, HotPads,
Apartments.com, Redfin). Reads Gmail over IMAP, read-only, with the same app password used for sending.

Alert emails differ per site, so parsing is generic: every listing card in these emails wraps its
photo/price/address in one tracking link, so anchors are grouped by href and any group showing a
$price becomes a listing."""
import email
import hashlib
import imaplib
import os
import re
from email.header import decode_header, make_header
from html import unescape

from ..model import ADDRESS_RE, Listing, clean_text, norm_address, parse_beds, parse_price

ANCHOR_RE = re.compile(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.S | re.I)


def _html_body(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    return ""


def parse_alert(html, site, assume=None):
    """Turn one alert email into Listings. Exposed for tests."""
    groups = {}
    for href, inner in ANCHOR_RE.findall(html):
        txt = clean_text(inner)
        img = re.search(r'<img[^>]+src="([^"]+)"', inner, re.I)
        g = groups.setdefault(unescape(href), {"text": [], "photo": ""})
        if txt:
            g["text"].append(txt)
        if img and not g["photo"]:
            g["photo"] = unescape(img.group(1))
    out = []
    for href, g in groups.items():
        text = " · ".join(dict.fromkeys(g["text"]))   # dedupe repeated anchor text, keep order
        price = parse_price(text)
        if not price or len(text) > 600:              # footer/nav links don't carry a price
            continue
        addr = ADDRESS_RE.search(text)
        address = addr.group(0) if addr else ""
        beds = parse_beds(text)
        key = norm_address(address) or hashlib.sha1(text.encode()).hexdigest()[:12]
        out.append(Listing(
            id=f"mail:{site}:{key}:{beds}",
            source=f"{site} alert",
            url=href,
            title=text[:140],
            price=price,
            beds=beds,
            address=f"{address}, San Francisco, CA" if address else "",
            text=text,
            photo=g["photo"],
            furnished=(assume or {}).get("furnished"),
            in_unit_wd=(assume or {}).get("in_unit_wd"),
        ))
    return out


def search(cfg, crit):
    user, pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw):
        print("  alertmail: GMAIL_USER / GMAIL_APP_PASSWORD not set, skipping")
        return []
    out = {}
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(user, pw)
        imap.select('"[Gmail]/All Mail"', readonly=True)   # read-only: never marks alerts as read
        for s in cfg["senders"]:
            q = f'from:({s["from"]}) newer_than:{cfg.get("days", 3)}d'
            typ, data = imap.search(None, "X-GM-RAW", f'"{q}"')
            for num in (data[0].split() if typ == "OK" else [])[-40:]:
                typ, msg_data = imap.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                subject = str(make_header(decode_header(msg.get("Subject", ""))))
                for l in parse_alert(_html_body(msg), s["name"], s.get("assume")):
                    l.text += f"\n(alert: {subject})"
                    out.setdefault(l.id, l)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return list(out.values())


def details(l):
    return l   # the source sites block scrapers; neighborhood comes from geocoding the address
