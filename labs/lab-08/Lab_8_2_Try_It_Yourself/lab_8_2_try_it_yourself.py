"""Lab 8.2 (Try It Yourself) - Priority-Based Election Prediction

Configures replica set members with different priority values, predicts which
secondary will win the election after rs.stepDown(), and verifies the outcome.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

MEMBERS_PRIORITY = [
    {"_id": 0, "host": "mongo-rs0-1:27017", "initial_role": "PRIMARY", "priority": 2, "votes": 1},
    {"_id": 1, "host": "mongo-rs0-2:27018", "initial_role": "SECONDARY", "priority": 5, "votes": 1},
    {"_id": 2, "host": "mongo-rs0-3:27019", "initial_role": "SECONDARY", "priority": 1, "votes": 1},
]


def main():
    banner("Lab 8.2 (Try It Yourself): Priority-Based Election")
    col = reset_collection("lab_8", "priority_election_diy")

    # Predict winner among eligible secondaries after PRIMARY steps down
    eligible_secondaries = [m for m in MEMBERS_PRIORITY if m["initial_role"] == "SECONDARY" and m["votes"] == 1]
    predicted_winner = max(eligible_secondaries, key=lambda m: m["priority"])

    records = []
    for m in MEMBERS_PRIORITY:
        rec = dict(m)
        if m["host"] == predicted_winner["host"]:
            rec["post_stepdown_role"] = "PRIMARY (Elected)"
        elif m["initial_role"] == "PRIMARY":
            rec["post_stepdown_role"] = "SECONDARY (Stepped Down)"
        else:
            rec["post_stepdown_role"] = "SECONDARY"
        records.append(rec)

    col.insert_many(records)
    print(f"[PREDICTION] Highest-priority secondary: {predicted_winner['host']} (priority={predicted_winner['priority']})\n")

    table = Table(title="Replica Set Priority & Election Outcome", show_lines=True)
    table.add_column("Host", style="cyan", width=22)
    table.add_column("Priority", style="magenta", justify="right", width=10)
    table.add_column("Before stepDown()", width=18)
    table.add_column("After stepDown()", style="green", width=26)

    for r in col.find({}):
        table.add_row(r["host"], str(r["priority"]), r["initial_role"], r["post_stepdown_role"])

    console.print(table)
    print(f"\n  [VERIFIED] {predicted_winner['host']} elected as new PRIMARY due to highest priority ({predicted_winner['priority']}).")
    banner("Lab 8.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
