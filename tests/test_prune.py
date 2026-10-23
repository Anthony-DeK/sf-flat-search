from types import SimpleNamespace

from scraper import http
from scraper.adapters import appfolio, craigslist, rentsfnow, zumper


def resp(status=200, url="", text="", json=None):
    return SimpleNamespace(status_code=status, ok=status < 400, url=url, text=text, json=lambda: json or {})


def fake(monkeypatch, r):
    monkeypatch.setattr(http, "get_any", lambda url, **kw: r)


def test_craigslist(monkeypatch):
    rec = {"url": "https://sfbay.craigslist.org/sfc/apa/d/x/1.html"}
    for status, want in [(410, False), (404, False), (200, True), (403, None)]:
        fake(monkeypatch, resp(status))
        assert craigslist.still_listed(rec) is want, status


def test_appfolio_redirect_to_index(monkeypatch):
    rec = {"url": "https://spsf.appfolio.com/listings/detail/abc"}
    fake(monkeypatch, resp(url="https://spsf.appfolio.com/listings/listings"))
    assert appfolio.still_listed(rec) is False
    fake(monkeypatch, resp(url=rec["url"]))
    assert appfolio.still_listed(rec) is True


def test_rentsfnow_banner(monkeypatch):
    rec = {"url": "https://www.rentsfnow.com/apartments/rental/57-taylor-334"}
    fake(monkeypatch, resp(text="<h2>Apartment No Longer Available</h2>"))
    assert rentsfnow.still_listed(rec) is False
    fake(monkeypatch, resp(text="<h2>300 Buchanan #407</h2>"))
    assert rentsfnow.still_listed(rec) is True


def test_zumper_status(monkeypatch):
    rec = {"id": "zumper:40871254"}
    for status, ls, want in [(200, 1, True), (200, 6, False), (404, None, False), (503, None, None)]:
        fake(monkeypatch, resp(status, json={"listing_status": ls}))
        assert zumper.still_listed(rec) is want, (status, ls)
