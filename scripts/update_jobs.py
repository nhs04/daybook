#!/usr/bin/env python3
"""Fetch new-grad and early-career tech jobs for Daybook.

Source: the SimplifyJobs New-Grad-Positions list (updated several times a day),
https://github.com/SimplifyJobs/New-Grad-Positions

Keeps open roles in New York City, California and the Boston area, newest first,
and writes a small JSON file the Daybook page reads:

    {"updated": "...", "source": "...", "counts": {...}, "jobs": [ {...}, ... ]}

Usage:  python3 update_jobs.py --out jobs.json
No third-party packages needed.
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

SOURCE_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
SOURCE_PAGE = "https://github.com/SimplifyJobs/New-Grad-Positions"

# How many roles to keep per region (newest first). Keeps the file small
# enough to load fast on a phone and to fit in Claude's storage.
CAPS = {"ny": 320, "ca": 220, "bos": 120}

NY_WORDS = ("new york, ny", "new york city", "nyc", "manhattan", "brooklyn", "queens, ny",
            "long island city", "jersey city", "hoboken")
CA_WORDS = (", ca", "california", "san francisco", "bay area", "los angeles", "silicon valley")
BOS_WORDS = ("boston", "cambridge, ma", "somerville, ma", "waltham, ma", "burlington, ma", "lexington, ma")


def regions_for(locations):
    found = []
    text = [l.lower() for l in locations]
    if any(w in l for l in text for w in NY_WORDS):
        found.append("ny")
    if any(w in l for l in text for w in CA_WORDS) or any(l in ("sf", "sf bay area", "la") for l in text):
        found.append("ca")
    if any(w in l for l in text for w in BOS_WORDS):
        found.append("bos")
    return found


def fetch_listings():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "daybook-jobs/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def build(listings):
    picked = []
    for x in listings:
        if not x.get("active") or not x.get("is_visible", True):
            continue
        url = x.get("url") or ""
        if not url.startswith("http"):
            continue
        locations = [str(l) for l in (x.get("locations") or [])]
        regions = regions_for(locations)
        if not regions:
            continue
        sponsorship = x.get("sponsorship") or ""
        picked.append({
            "id": str(x.get("id") or url)[:80],
            "company": str(x.get("company_name") or "").strip()[:80],
            "title": str(x.get("title") or "").strip()[:140],
            "url": url[:600],
            "locations": locations[:4],
            "regions": regions,
            "category": str(x.get("category") or "").strip()[:40],
            "posted": int(x.get("date_posted") or 0),
            "sponsorship": "" if sponsorship == "Other" else sponsorship[:60],
        })

    picked.sort(key=lambda j: j["posted"], reverse=True)
    kept, seen, per = [], set(), {k: 0 for k in CAPS}
    for j in picked:
        if j["id"] in seen:
            continue
        if not any(per[r] < CAPS[r] for r in j["regions"]):
            continue
        for r in j["regions"]:
            per[r] += 1
        seen.add(j["id"])
        kept.append(j)

    now = time.time()
    counts = {
        r: {
            "open": sum(1 for j in picked if r in j["regions"]),
            "new_today": sum(1 for j in picked if r in j["regions"] and now - j["posted"] < 36 * 3600),
            "this_week": sum(1 for j in picked if r in j["regions"] and now - j["posted"] < 7 * 86400),
        }
        for r in CAPS
    }
    return {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE_PAGE,
        "counts": counts,
        "jobs": kept,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="jobs.json")
    args = ap.parse_args()
    try:
        data = build(fetch_listings())
    except Exception as e:  # keep yesterday's file if the source is down
        print(f"Could not refresh jobs: {e}", file=sys.stderr)
        sys.exit(1)
    if not data["jobs"]:
        print("Source returned no matching jobs; keeping the previous file.", file=sys.stderr)
        sys.exit(1)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    c = data["counts"]
    print(f"Saved {len(data['jobs'])} jobs to {args.out} · New York {c['ny']['open']} open ({c['ny']['new_today']} new) · "
          f"California {c['ca']['open']} · Boston {c['bos']['open']}")


if __name__ == "__main__":
    main()
