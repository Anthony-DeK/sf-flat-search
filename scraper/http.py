import time

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def get(url, **kw):
    kw.setdefault("timeout", 25)
    r = _session.get(url, **kw)
    r.raise_for_status()
    return r


def post(url, **kw):
    kw.setdefault("timeout", 25)
    r = _session.post(url, **kw)
    r.raise_for_status()
    return r


def pause(seconds=1.5):
    """Spacing between detail-page fetches so we stay a polite, low-volume client."""
    time.sleep(seconds)
