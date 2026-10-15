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
    for t in ["coin-op laundry in basement", "shared laundry", "laundry on site", "Laundry in building",
              "Features: Dishwasher | Onsite Laundry", "Features: Laundry Shared"]:
        ev = evaluate(L(text=f"furnished. {t}", hood_text="noe valley"))
        assert ev["status"] == "reject" and "no in-unit W/D" in ev["reasons"], t


def test_furnishing_is_a_label():
    ev = evaluate(L(text="Unfurnished. In-unit W/D.", hood_text="nob hill"))
    assert ev["status"] == "match" and ev["furnished"] is False
    assert evaluate(L(text="Fully furnished, in-unit W/D", hood_text="nob hill"))["furnished"] is True
    assert evaluate(L(text="In-unit W/D", hood_text="nob hill"))["furnished"] is None
    assert evaluate(L(text="Available furnished or unfurnished. In-unit W/D", hood_text="nob hill"))["furnished"] is None


def test_require_furnished_switch():
    import copy
    from scraper.filter import CRITERIA
    crit = copy.deepcopy(CRITERIA)
    crit["furnishing"]["require_furnished"] = True
    assert "no furnished" in evaluate(L(text="Unfurnished. In-unit W/D.", hood_text="nob hill"), crit)["reasons"]


def test_silent_listing_is_maybe():
    ev = evaluate(L(text="Sunny 1BR with views", hood_text="cow hollow"))
    assert ev["status"] == "maybe"
    assert set(ev["unknown"]) == {"in-unit W/D"}
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
    assert neighborhood(L(lat=37.7550, lon=-122.4950, hood_text="nob hill"))[0] is None   # Outer Sunset
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


def test_new_neighborhoods():
    assert neighborhood(L(lat=37.7890, lon=-122.4350))[0] == "Pacific Heights"
    assert neighborhood(L(lat=37.7765, lon=-122.4245))[0] == "Hayes Valley"
    assert neighborhood(L(lat=37.7610, lon=-122.4390))[0] == "Castro"
    assert neighborhood(L(lat=37.7859, lon=-122.3928))[0] == "East SoMa / Mission Bay"   # South Beach
    assert neighborhood(L(lat=37.7700, lon=-122.3910))[0] == "East SoMa / Mission Bay"   # Mission Bay
    assert neighborhood(L(lat=37.7754, lon=-122.4130))[0] == "West SoMa"                 # 1288 Howard
    assert neighborhood(L(lat=37.7801, lon=-122.4038))[0] == "Central SoMa"              # 900 Folsom
    assert neighborhood(L(hood_text="SOMA")) == ("SoMa (unsure which part)", False)
    assert neighborhood(L(lat=37.7830, lon=-122.4150))[0] is None           # Tenderloin, north of Market
    assert neighborhood(L(hood_text="lower pac hts")) == ("Pacific Heights", True)
    assert neighborhood(L(hood_text="hayward / castro valley"))[0] is None


def test_alert_email_parser():
    from scraper.adapters.alertmail import parse_alert
    html = """
    <a href="https://click.zillow.com/abc"><img src="https://photos/1.jpg"></a>
    <a href="https://click.zillow.com/abc">$3,850/mo</a>
    <a href="https://click.zillow.com/abc">1 bd · 1 ba · 650 sqft</a>
    <a href="https://click.zillow.com/abc">1450 Washington St #4, San Francisco, CA 94109</a>
    <a href="https://click.zillow.com/xyz">$4,400/mo 2 bds 2200 Pacific Ave APT 3, San Francisco</a>
    <a href="https://zillow.com/unsubscribe">Unsubscribe</a>
    """
    ls = parse_alert(html, "Zillow", {"furnished": True})
    assert [(l.price, l.beds) for l in ls] == [(3850, 1), (4400, 2)]
    assert ls[0].address.startswith("1450 Washington St #4")
    assert ls[0].photo == "https://photos/1.jpg" and ls[0].furnished is True


def test_market_corridor_excluded():
    ev = evaluate(L(lat=37.7800, lon=-122.4100, text="furnished, in-unit laundry"))   # 6th & Mission
    assert ev["status"] == "reject" and ev["reasons"][0].startswith("excluded area")
    assert "not residential" in evaluate(L(title="Spacious Garage Parking - Close to Jasper"))["reasons"]


def test_in_unit_beats_building_laundry():
    ev = evaluate(L(text="In-unit washer/dryer. Building also has a laundry room.", hood_text="nob hill"))
    assert ev["in_unit_wd"] is True
