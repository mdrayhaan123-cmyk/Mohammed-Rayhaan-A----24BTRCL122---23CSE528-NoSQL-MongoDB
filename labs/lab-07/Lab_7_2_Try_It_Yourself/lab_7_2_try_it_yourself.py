"""Lab 7.2 (Try It Yourself) - WiredTiger Cache & New Threat Report Monitor

Polls db.serverStatus() WiredTiger cache metrics every 10 seconds and checks
for newer threat reports (from awesome-annual-security-reports) not yet in lab_7.
"""

import argparse
import sys, os, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.connection import get_db, reset_collection, banner

UPSTREAM_REPORTS_FEED = [
    {"report_id": "CTI-2026-001", "title": "Check Point Cybersecurity Report 2026", "vendor": "Check Point", "category": "Ransomware"},
    {"report_id": "CTI-2026-007", "title": "GuidePoint GRIT Ransomware Annual Report 2026", "vendor": "GuidePoint", "category": "Ransomware"},
    {"report_id": "CTI-2026-008", "title": "Datadog State of DevSecOps 2026", "vendor": "Datadog", "category": "Application Security"},
]


def check_newer_reports(db):
    existing_ids = {d["report_id"] for d in db["threat_reports"].find({}, {"report_id": 1, "_id": 0})}
    return [r for r in UPSTREAM_REPORTS_FEED if r["report_id"] not in existing_ids]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=10.0, help="Polling interval in seconds (default 10s)")
    parser.add_argument("--cycles", type=int, default=2, help="Number of monitoring cycles")
    args = parser.parse_args()

    banner("Lab 7.2 (Try It Yourself): Cache & Threat Feed Monitor")
    db = get_db("lab_7")
    log_col = reset_collection("lab_7", "cache_monitor_log")

    for cycle in range(1, args.cycles + 1):
        cache = db.command("serverStatus").get("wiredTiger", {}).get("cache", {})
        pages_read = cache.get("pages read into cache", 0)
        pages_evict = cache.get("eviction pages evicted by application threads", 0)
        hit_ratio = round(max(0.0, 1.0 - (pages_evict / pages_read)) * 100, 2) if pages_read else 100.0
        newer = check_newer_reports(db)

        entry = {
            "cycle": cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_used_bytes": cache.get("bytes currently in the cache", 0),
            "hit_ratio_pct": hit_ratio,
            "new_reports_found": [r["report_id"] for r in newer],
        }
        log_col.insert_one(entry)
        print(f"[Cycle {cycle}] Hit Ratio: {hit_ratio}% | Newer Reports Not in DB: {entry['new_reports_found']}")
        if cycle < args.cycles:
            time.sleep(args.interval)

    banner("Lab 7.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
