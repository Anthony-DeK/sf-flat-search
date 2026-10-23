"""Weekly: re-open every kept listing's URL and delete the ones taken down.
python -m scraper.prune [--dry-run] [--source NAME]

A deleted listing's id goes into data/removed.json so a stale search result can't bring it back
(and re-alert). Sources with no reliable "gone" signal (Reddit, alert emails) are left alone."""
import argparse
import importlib
from collections import Counter
from datetime import timedelta

from . import http
from .run import PUBLIC, REMOVED, STATE, load, now, save

FORGET_REMOVED_AFTER = timedelta(days=90)
ADAPTER = {"mail": "alertmail"}       # id prefix -> adapter module, where they differ
MIN_TO_TRUST_ALL_GONE = 5             # every listing of a source "gone" at once smells like a site change


def checker(rec):
    prefix = rec["id"].split(":", 1)[0]
    try:
        mod = importlib.import_module(f".adapters.{ADAPTER.get(prefix, prefix)}", __package__)
    except ModuleNotFoundError:
        return None
    return getattr(mod, "still_listed", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report what would be removed; save nothing")
    ap.add_argument("--source", help="only check listings whose id starts with this, e.g. craigslist")
    args = ap.parse_args()

    state = load(STATE, {})
    removed = load(REMOVED, {})
    t = now().isoformat(timespec="seconds")
    results = {}   # prefix -> {id: True / False / None}

    # Rejects are never shown and already expire after 14 days unseen; not worth the requests.
    todo = [r for r in state.values() if r["status"] != "reject"
            and (not args.source or r["id"].startswith(args.source.lower()))]
    for r in todo:
        prefix = r["id"].split(":", 1)[0]
        check = checker(r)
        if not check:
            results.setdefault(prefix, {})[r["id"]] = None
            continue
        http.pause(1)
        try:
            results.setdefault(prefix, {})[r["id"]] = check(r)
        except Exception as e:
            print(f"  check failed {r['url']}: {e}")
            results.setdefault(prefix, {})[r["id"]] = None

    gone = []
    for prefix, res in sorted(results.items()):
        c = Counter("gone" if v is False else "live" if v else "unknown" for v in res.values())
        note = ""
        if c["gone"] >= MIN_TO_TRUST_ALL_GONE and c["gone"] == len(res):
            note = " · all gone, assuming the check broke; nothing removed"
        else:
            gone += [i for i, v in res.items() if v is False]
        print(f"{prefix}: {len(res)} checked · {dict(c)}{note}")

    for i in gone:
        print(f"  gone: {state[i]['title'][:70]} · {state[i]['url']}")
        state.pop(i)
        removed[i] = t
    cutoff = now() - FORGET_REMOVED_AFTER
    removed = {i: ts for i, ts in removed.items() if ts >= cutoff.isoformat(timespec="seconds")}
    print(f"\nremoved {len(gone)} listings")

    if args.dry_run:
        return
    save(STATE, state)
    save(REMOVED, removed)
    public = load(PUBLIC, None)
    if public:
        public["listings"] = [l for l in public["listings"] if l["id"] not in removed]
        save(PUBLIC, public)


if __name__ == "__main__":
    main()
