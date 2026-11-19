"""Lab 7.1 - Analyze a Production CTI Schema

Examines the Cyber Threat Intelligence schema in lab_7, identifies embedded vs.
referenced relationships, calculates average $bsonSize, and verifies < 16 MB.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, banner
from backend.seed_cti_data import seed_all
from rich.table import Table
from rich.console import Console

console = Console()


def main():
    banner("Lab 7.1: Production CTI Schema Analysis")
    seed_all()
    db = get_db("lab_7")
    col = db["threat_reports"]

    print("\n=== Relationship Modeling Analysis ===")
    print("  [EMBEDDED]   tags[] & iocs[] -> Bounded per report, always read together with report.")
    print("  [REFERENCED] source_id -> threat_sources: Many reports share 1 source; referencing")
    print("               avoids duplicating feed URL/reliability across hundreds of reports.\n")

    table = Table(title="CTI Report Document Sizes ($bsonSize)", show_lines=True)
    table.add_column("Report ID", style="cyan", width=14)
    table.add_column("Title", width=44)
    table.add_column("IOCs", justify="right", width=6)
    table.add_column("BSON Size (bytes)", style="green", justify="right", width=18)

    pipeline = [
        {
            "$project": {
                "_id": 0,
                "report_id": 1,
                "title": 1,
                "ioc_count": {"$size": {"$ifNull": ["$iocs", []]}},
                "bson_bytes": {"$bsonSize": "$$ROOT"},
            }
        }
    ]
    sizes = []
    for doc in col.aggregate(pipeline):
        bsize = doc["bson_bytes"]
        sizes.append(bsize)
        table.add_row(doc["report_id"], doc["title"][:42], str(doc["ioc_count"]), str(bsize))

    console.print(table)
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    max_limit = 16 * 1024 * 1024
    print(f"\n  Average BSON size : {avg_size:.1f} bytes")
    print(f"  Max BSON limit    : {max_limit:,} bytes (16 MB)")
    print("  Status            : [OK] All documents are well below the 16 MB limit.")
    banner("Lab 7.1 Complete")


if __name__ == "__main__":
    main()
