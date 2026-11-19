"""Lab 8.1 (Try It Yourself) - Replica Set with Arbiter Node

Models a 3-member replica set (2 data-bearing nodes + 1 arbiterOnly node),
stores the topology in lab_8.arbiter_topology, and explains why arbiters
provide odd-number voting quorum without full storage cost.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

ARBITER_MEMBERS = [
    {"_id": 0, "host": "mongo-rs0-1:27017", "role": "PRIMARY", "arbiterOnly": False, "votes": 1, "stores_data": True},
    {"_id": 1, "host": "mongo-rs0-2:27018", "role": "SECONDARY", "arbiterOnly": False, "votes": 1, "stores_data": True},
    {"_id": 2, "host": "mongo-rs0-3:27019", "role": "ARBITER", "arbiterOnly": True, "votes": 1, "stores_data": False},
]


def main():
    banner("Lab 8.1 (Try It Yourself): Arbiter Node Topology")
    col = reset_collection("lab_8", "arbiter_topology")
    col.insert_many(ARBITER_MEMBERS)
    print(f"[OK] Saved {len(ARBITER_MEMBERS)}-member arbiter topology in lab_8.arbiter_topology.\n")

    table = Table(title="Replica Set rs0 with Arbiter (2 Data + 1 Arbiter)", show_lines=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Host", width=22)
    table.add_column("Role", style="magenta", width=12)
    table.add_column("arbiterOnly", width=12)
    table.add_column("Votes", justify="right", width=6)
    table.add_column("Stores Data", style="green", width=12)

    for m in col.find({}):
        table.add_row(str(m["_id"]), m["host"], m["role"], str(m["arbiterOnly"]), str(m["votes"]), str(m["stores_data"]))

    console.print(table)

    print("\n--- Why Use an Arbiter? ---")
    print("  1. Odd Voting Quorum: 3 voting members tolerate 1 node failure without split-brain.")
    print("  2. Zero Data Storage Cost: An arbiter does NOT store a copy of the database.")
    print("  3. Tie-Breaker Only: Ideal when budget/disk limits allow only 2 full data nodes.")

    banner("Lab 8.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
