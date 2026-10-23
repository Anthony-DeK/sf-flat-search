import re
from dataclasses import dataclass, field, asdict


@dataclass
class Listing:
    id: str                      # "<source>:<native id>"
    source: str
    url: str
    title: str
    price: int | None = None
    beds: int | None = None      # 0 = studio
    baths: float | None = None
    sqft: int | None = None
    address: str = ""
    hood_text: str = ""          # neighborhood as labeled by the source
    lat: float | None = None
    lon: float | None = None
    text: str = ""               # full description, used for keyword checks
    photo: str = ""
    available: str = ""
    # Structured facts from the source override keyword guesses: True / False / None (unknown).
    furnished: bool | None = None
    in_unit_wd: bool | None = None
    lease: str = ""              # "12mo", "m2m", "6mo", ... or "" when unknown
    amenities: list[str] = field(default_factory=list)
    geo_tried: str = ""          # address last sent to the geocoder, so a failing one isn't retried every run

    def to_dict(self):
        return asdict(self)


ADDRESS_RE = re.compile(
    r"\b\d{1,5}[A-Z]?\s+(?:[A-Z0-9][\w'.-]*\s){1,4}"
    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Way|Pl|Place|Ter|Terrace|Dr|Drive|Ln|Lane|Ct|Court|Rd|Road|Aly|Alley|Hwy)\b"
    r"(?:[ ,]*(?:#|Apt|Unit|Ste)\s*[\w-]+)?", re.I)
# "2 blocks to Fillmore St", "1 bath, walk to Hayes St": a number followed by these words isn't a house number.
NOT_ADDRESS_RE = re.compile(r"\b(blocks?|min(ute)?s?|beds?|bedrooms?|baths?|br|ba|bd|walk|to|from|near|floors?|stor(y|ies))\b", re.I)
PRICE_RE = re.compile(r"\$\s?(\d{1,2},?\d{3})")
BEDS_RE = re.compile(r"\b(\d)\s*(?:br|bds?|beds?|bedrooms?)\b|\b(studio)\b", re.I)


def parse_price(s):
    m = PRICE_RE.search(s or "")
    return int(m.group(1).replace(",", "")) if m else None


def parse_beds(s):
    m = BEDS_RE.search(s or "")
    if not m:
        return None
    return 0 if m.group(2) else int(m.group(1))


def find_address(text):
    """First street address written in free text, e.g. "Welcome to 175 Bluxome Street!"."""
    for m in ADDRESS_RE.finditer(text or ""):
        if not NOT_ADDRESS_RE.search(m.group(0)):
            return m.group(0)
    return ""


def clean_text(html):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#36;", "$")
          .replace("&#39;", "'").replace("&quot;", '"'))
    return re.sub(r"[ \t]+", " ", s).strip()


def norm_address(addr):
    a = (addr or "").lower()
    a = re.sub(r"\b(san francisco|ca|california|usa)\b|\d{5}", " ", a)
    a = re.sub(r"\b(street)\b", "st", a)
    a = re.sub(r"\b(avenue)\b", "ave", a)
    a = re.sub(r"\b(apt|unit|suite|#)\s*", "#", a)
    return re.sub(r"[^a-z0-9#]+", " ", a).strip()
