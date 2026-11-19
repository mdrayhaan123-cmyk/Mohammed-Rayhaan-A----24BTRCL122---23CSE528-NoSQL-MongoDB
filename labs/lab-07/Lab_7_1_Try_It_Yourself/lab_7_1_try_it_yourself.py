"""Lab 7.1 (Try It Yourself) - Embedded Threat Source Redesign

Redesigns the threat_sources -> threat_reports reference into an embedded
'source_assessment' subdocument to evaluate which sources represent actual threats.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from backend.seed_cti_data import THREAT_REPORTS, THREAT_SOURCES
from rich.table import Table
from rich.console import Console

console = Console()


def main():
    banner("Lab 7.1 (Try It Yourself): Embedded Source Assessment")
    source_map = {s["source_id"]: s for s in THREAT_SOURCES}

    emb_col = reset_collection("lab_7", "threat_reports_embedded_diy")
    embedded_docs = []
    for r in THREAT_REPORTS:
        src = source_map.get(r["source_id"], {})
        doc = {k: v for k, v in r.items() if k != "source_id"}
        doc["source_assessment"] = {
            "source_id": r["source_id"],
            "name": src.get("name", "Unknown"),
            "reliability": src.get("reliability", "Unknown"),
            "is_actual_threat_feed": src.get("is_actual_threat_feed", False),
        }
        embedded_docs.append(doc)

    emb_col.insert_many(embedded_docs)
    print(f"[OK] Migrated {len(embedded_docs)} reports to embedded schema in lab_7.threat_reports_embedded_diy.\n")

    # Single-query filter without $lookup
    actual_threats = list(emb_col.find({"source_assessment.is_actual_threat_feed": True, "is_actual_threat": True}))
    print(f"=== Verified Actual Threats (Single find(), no $lookup): {len(actual_threats)} ===")
    for t in actual_threats:
        print(f"  {t['report_id']} | {t['source_assessment']['name']} | {t['title'][:55]}")

    table = Table(title="Trade-Offs: Embedded Source Assessment", show_lines=True)
    table.add_column("Operation", style="cyan", width=30)
    table.add_column("Impact in Embedded Design", width=60)
    table.add_row("Read report + threat status", "FASTER: Single find() query; eliminates $lookup join.")
    table.add_row("Filter by source reliability", "FASTER: Direct indexable query on source_assessment.reliability.")
    table.add_row("Update source reliability", "HARDER: Must update_many() across all reports from that source.")
    console.print(table)
    banner("Lab 7.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
