#!/usr/bin/env python3
"""
Sapphic Weekly ATX -> events.json for the Do512 & Chamber Listing Generator.

Reads the public Upcoming Events feed on sapphicweeklyatx.com and saves the
details the generator needs (title, venue, address, date, times, Partiful link)
to events.json next to index.html. Uses only the Python standard library.

Usage:
  python3 fetch_events.py                     # read the live website
  python3 fetch_events.py --feed-file f.json  # read a saved feed (for testing)
"""

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SITE = "https://www.sapphicweeklyatx.com"
FEED_URL = SITE + "/upcoming-events?format=json"
TZ = ZoneInfo("America/Chicago")
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.json")
STATES = {"texas": "TX"}
PARTIFUL = re.compile(r'href="(https?://(?:www\.)?partiful\.com/e/[^"?#]+)', re.IGNORECASE)


def load_feed(feed_file=None):
    if feed_file:
        with open(feed_file) as f:
            return json.load(f)
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "SapphicWeeklyListingGen/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def full_address(loc):
    """'1016 E 6th St' + 'Austin, Texas, 78702' -> '1016 E 6th St, Austin, TX 78702'"""
    line1 = (loc.get("addressLine1") or "").strip()
    parts = [p.strip() for p in (loc.get("addressLine2") or "").split(",")]
    city = parts[0] if parts else ""
    state = STATES.get(parts[1].lower(), parts[1]) if len(parts) > 1 else ""
    postal = parts[2] if len(parts) > 2 else ""
    tail = " ".join(x for x in [state, postal] if x)
    return ", ".join(x for x in [line1, city, tail] if x)


def local(ms):
    return datetime.fromtimestamp(ms / 1000, tz=TZ)


def simplify(ev):
    loc = ev.get("location") or {}
    start = local(ev["startDate"])
    end = local(ev["endDate"]) if ev.get("endDate") else None
    match = PARTIFUL.search(ev.get("body") or "")
    return {
        "id": ev.get("id"),
        "title": (ev.get("title") or "").strip(),
        "venue": (loc.get("addressTitle") or "").strip(),
        "address": full_address(loc),
        "date": start.strftime("%Y-%m-%d"),
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M") if end else "",
        "partiful": match.group(1) if match else "",
        "url": SITE + (ev.get("fullUrl") or ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed-file", help="read the website feed from a saved file (for testing)")
    args = ap.parse_args()

    feed = load_feed(args.feed_file)
    now_ms = time.time() * 1000
    # Keep events until 12 hours after they end, so tonight's event stays listed during the event
    # (the video upload page uses this list too)
    keep_after = now_ms - 12 * 3600 * 1000
    upcoming = [e for e in feed.get("upcoming", []) + feed.get("past", [])
                if (e.get("endDate") or e.get("startDate") or 0) > keep_after]
    seen = set()
    upcoming = [e for e in upcoming if not (e.get("id") in seen or seen.add(e.get("id")))]
    upcoming.sort(key=lambda e: e["startDate"])
    events = [simplify(e) for e in upcoming]

    # Only rewrite the file when the events change, so the repo isn't
    # flooded with commits that just bump a timestamp.
    try:
        with open(OUT_FILE) as f:
            old = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        old = {}
    if old.get("events") == events:
        print(f"No changes ({len(events)} upcoming events).")
        return

    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "events": events,
    }
    with open(OUT_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Saved {len(events)} upcoming events to events.json:")
    for e in events:
        missing = [k for k in ("venue", "address", "partiful") if not e[k]]
        note = f"  (missing: {', '.join(missing)})" if missing else ""
        print(f"  {e['date']} {e['start']}  {e['title']}{note}")


if __name__ == "__main__":
    main()
