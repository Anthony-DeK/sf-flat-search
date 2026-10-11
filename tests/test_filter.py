from scraper.filter import evaluate, neighborhood
from scraper.model import Listing, parse_beds, parse_price


def L(**kw):
    base = dict(id="t:1", source="t", url="u", title="", price=3500, beds=1)
    return Listing(**{**base, **kw})


# Real Craigslist post body (690 Sutter, 2026-10-11)
SUTTER = """Executive 1BR/1BA
* $3,495/month annual lease
* Fully furnished executive residence
* In-unit washer & dryer
* Prime Nob Hill address"""


def test_real_post_matches():
    ev = evaluate(L(title="Stunning 1BR", text=SUTTER, lat=37.7889, lon=-122.4114))
    assert ev["status"] == "match"
    assert ev["hood"] == "Nob Hill"
    assert ev["lease"] == "12mo"


def test_wd_phrasings():
    for t in ["in-unit laundry", "Washer/dryer in unit", "W/D in unit", "washer and dryer inside the apartment",
              "Laundry in unit", "in unit washer"]:
        assert evaluate(L(text=f"furnished. {t}", hood_text="noe valley"))["in_unit_wd"] is True, t


def test_wd_rejections():
    for t in ["coin-op laundry in basement", "shared laundry", "laundry on site", "Laundry in building"]:
        ev = evaluate(L(text=f"furnished. {t}", hood_text="noe valley"))
        assert ev["status"] == "reject" and "no in-unit W/D" in ev["reasons"], t


def test_unfurnished_is_rejected_not_matched():
    ev = evaluate(L(text="Unfurnished. In-unit W/D.", hood_text="nob hill"))
    assert "no furnished" in ev["reasons"]


def test_silent_listing_is_maybe():
    ev = evaluate(L(text="Sunny 1BR with views", hood_text="cow hollow"))
    assert ev["status"] == "maybe"
    assert set(ev["unknown"]) == {"furnished", "in-unit W/D"}
    assert "views" in ev["bonus"]


def test_structured_flags_beat_keywords():
    # Blueground marks laundry absent structurally even if the blurb says "laundry".
    ev = evaluate(L(text="laundry in unit", hood_text="cow hollow", furnished=True, in_unit_wd=False))
    assert "no in-unit W/D" in ev["reasons"]


def test_hard_filters():
    assert "price $5995" in evaluate(L(price=5995, hood_text="nob hill"))["reasons"]
    assert "0 beds" in evaluate(L(beds=0, hood_text="nob hill"))["reasons"]
    assert "3 beds" in evaluate(L(beds=3, hood_text="nob hill"))["reasons"]
    assert "not residential" in evaluate(L(title="Large commercial space on Mason"))["reasons"]


def test_neighborhood_by_coords():
    assert neighborhood(L(lat=37.8005, lon=-122.4100))[0] == "North Beach"
    assert neighborhood(L(lat=37.7990, lon=-122.4360))[0] == "Cow Hollow"
    assert neighborhood(L(lat=37.7510, lon=-122.4330))[0] == "Noe Valley"
    assert neighborhood(L(lat=37.7620, lon=-122.4260))[0] == "Mission Dolores"
    # Coordinates outside every box win over a "near Nob Hill" mention.
    assert neighborhood(L(lat=37.7790, lon=-122.3950, hood_text="nob hill"))[0] is None   # SoMa
    assert neighborhood(L(lat=37.7880, lon=-122.4075))[0] is None                         # Union Square


def test_neighborhood_text_confidence():
    assert neighborhood(L(hood_text="lower nob hill")) == ("Nob Hill", True)
    assert neighborhood(L(text="5 min walk to North Beach")) == ("North Beach", False)
    assert neighborhood(L(address="535 Leavenworth St, San Francisco, CA 94109")) == ("zip 94109", False)


def test_lease_terms():
    assert evaluate(L(text="month-to-month ok"))["lease"] == "m2m"
    assert evaluate(L(text="6 month lease"))["lease"] == "6mo"
    assert evaluate(L(text="1 year lease"))["lease"] == "12mo"


def test_parsers():
    assert parse_price("Rent: $3,495/mo") == 3495
    assert parse_beds("Sunny 2BR/1BA") == 2
    assert parse_beds("Big studio") == 0
