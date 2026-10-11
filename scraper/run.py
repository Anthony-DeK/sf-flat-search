"""Entry point: python -m scraper.run [--dry-run] [--source NAME] [--max-details N]"""
import argparse
import importlib
import json
import os
import statistics
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import geo, http, notify
from .filter import CRITERIA, evaluate
from .model import Listing, norm_address

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "listings.json"
HEALTH = ROOT / "data" / "health.json"
PUBLIC = ROOT / "docs" / "listings.json"
STALE_AFTER = timedelta(days=3)       # unseen this long -> inactive (rented / taken down)
DROP_REJECTS_AFTER = timedelta(days=14)
DETAIL_FIELDS = ("text", "address", "photo", "price", "in_unit_wd", "furnished", "amenities", "lat", "lon", "available")


def now():
    return datetime.now(timezone.utc)


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def prefilter_rejects(l, ev):
    """Rejections we trust before fetching details. Neighborhood isn't one of them when coords may come later."""
    return [r for r in ev["reasons"] if not (r.startswith("outside") and l.lat is None)]


def deal_flags(records):
    """Flag listings in the cheapest quartile of price-per-bedroom within their neighborhood."""
    by_hood = {}
    for r in records.values():
        if r["status"] != "reject" and r.get("price") and r.get("beds") and r.get("hood_confident"):
            by_hood.setdefault(r["hood"], []).append(r["price"] / r["beds"])
    for r in records.values():
        vals = by_hood.get(r.get("hood"), [])
        r["deal"] = bool(len(vals) >= 6 and r.get("price") and r.get("beds")
                         and r["price"] / r["beds"] <= statistics.quantiles(vals, n=4)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print alerts instead of sending; don't save state")
    ap.add_argument("--source", help="only run sources whose name contains this")
    ap.add_argument("--max-details", type=int, default=int(os.environ.get("MAX_DETAILS", 60)))
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    state = load(STATE, {})
    health = load(HEALTH, {})
    t = now().isoformat(timespec="seconds")
    details_left = args.max_details
    new_matches, new_maybes = [], []

    for src in cfg["sources"]:
        if args.source and args.source.lower() not in src["name"].lower():
            continue
        adapter = importlib.import_module(f".adapters.{src['adapter']}", __package__)
        h = health.setdefault(src["name"], {})
        h.setdefault("zero_runs", 0)
        h.setdefault("error_runs", 0)
        h["can_be_empty"] = src.get("can_be_empty", False)
        try:
            found = adapter.search(src, CRITERIA)
            h.update(last_count=len(found), last_ok=t, last_error=None, error_runs=0)
            h["zero_runs"] = 0 if found else h["zero_runs"] + 1
        except Exception as e:
            traceback.print_exc()
            h.update(last_count=0, last_error=f"{type(e).__name__}: {e}"[:300])
            h["error_runs"] += 1
            continue

        stats = {"match": 0, "maybe": 0, "reject": 0, "new": 0}
        for l in found:
            prev = state.get(l.id)
            if prev:  # reuse detail-page facts from earlier runs
                for f in DETAIL_FIELDS:
                    if prev.get(f) not in (None, "", []) and getattr(l, f) in (None, "", []):
                        setattr(l, f, prev[f])
            ev = evaluate(l)
            needs_detail = not (prev and prev.get("detailed")) and not prefilter_rejects(l, ev)
            if needs_detail and details_left > 0:
                details_left -= 1
                try:
                    http.pause()
                    adapter.details(l)
                    if l.lat is None and (ll := geo.geocode(l.address)):
                        l.lat, l.lon = ll
                    ev = evaluate(l)
                    detailed = True
                except Exception as e:
                    print(f"  details failed {l.url}: {e}")
                    detailed = False
            else:
                detailed = bool(prev and prev.get("detailed")) or not needs_detail

            rec = {**l.to_dict(), **ev, "hood_confident": "neighborhood" not in ev["unknown"] and ev["hood"] is not None,
                   "detailed": detailed, "last_seen": t, "active": True,
                   "first_seen": prev["first_seen"] if prev else t,
                   "alerted": prev.get("alerted", False) if prev else False,
                   "price_history": (prev or {}).get("price_history", [])}
            if l.price and (not rec["price_history"] or rec["price_history"][-1][1] != l.price):
                rec["price_history"].append([t, l.price])
            state[l.id] = rec
            stats[ev["status"]] += 1
            stats["new"] += not prev
        print(f"{src['name']}: {len(found)} found · {stats}")

    cutoff = now() - STALE_AFTER
    for r in state.values():
        r["active"] = datetime.fromisoformat(r["last_seen"]) >= cutoff

    # Duplicates (reposts, or one unit on several sites): keep the earliest record, link the others.
    owner = {}
    for r in sorted(state.values(), key=lambda r: r["first_seen"]):
        r.pop("duplicate_of", None)
        r.pop("also_on", None)
    for r in sorted(state.values(), key=lambda r: r["first_seen"]):
        if r["status"] == "reject" or not r["active"]:
            continue
        keys = []
        addr = norm_address(r.get("address"))
        if len(addr) >= 6:
            keys.append(("addr", addr, r.get("beds")))
        if r.get("lat") is not None and r.get("price"):
            # ~100 m grid; craigslist pins and geocoded addresses rarely agree more precisely than that
            keys.append(("geo", round(r["lat"], 3), round(r["lon"], 3), r.get("beds"), r["price"]))
        first = next((owner[k] for k in keys if k in owner and owner[k] != r["id"]), None)
        if first:
            r["duplicate_of"] = first
            state[first].setdefault("also_on", []).append(r["url"])
        else:
            for k in keys:
                owner.setdefault(k, r["id"])

    deal_flags(state)

    for r in state.values():
        if r["active"] and not r["alerted"] and r["detailed"] and not r.get("duplicate_of"):
            if r["status"] == "match":
                new_matches.append(r)
            elif r["status"] == "maybe":
                new_maybes.append(r)
    # Alert once, when a threshold is first crossed: 2 failing runs, or 4 empty runs (~2h) for sources that never go empty.
    broken = [f"{n}: {h['last_error']} ({h['error_runs']} failed runs)" for n, h in health.items() if h["error_runs"] == 2]
    broken += [f"{n}: returned 0 listings {h['zero_runs']} runs in a row (site layout may have changed)"
               for n, h in health.items() if h["zero_runs"] == 4 and not h["can_be_empty"]]

    new_matches.sort(key=lambda r: (not r["deal"], r["price"] or 1e9))
    print(f"\nnew matches: {len(new_matches)} · new maybes: {len(new_maybes)} · broken: {len(broken)}")
    notify.push(new_matches, dry_run=args.dry_run)
    notify.email(new_matches, new_maybes, broken, os.environ.get("DASHBOARD_URL", ""), dry_run=args.dry_run)

    if args.dry_run:
        return
    for r in new_matches + new_maybes:
        state[r["id"]]["alerted"] = True
    drop_before = now() - DROP_REJECTS_AFTER
    state = {k: v for k, v in state.items()
             if not (v["status"] == "reject" and datetime.fromisoformat(v["last_seen"]) < drop_before)}
    save(STATE, state)
    save(HEALTH, health)
    public = [{k: v for k, v in r.items() if k not in ("text", "detailed", "alerted")} | {"snippet": r["text"][:400]}
              for r in state.values() if r["status"] != "reject" and not r.get("duplicate_of")]
    save(PUBLIC, {"updated": t, "listings": public, "health": health, "manual": cfg.get("manual", [])})


if __name__ == "__main__":
    main()
