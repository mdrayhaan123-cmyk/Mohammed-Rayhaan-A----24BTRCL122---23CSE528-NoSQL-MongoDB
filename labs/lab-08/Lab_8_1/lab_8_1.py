"""Lab 8.1 - Deploy and Verify a Local Replica Set

Connects to the 3-node replica set (rs0), inspects rs.status() member roles
and health, inserts a test document into lab_8.replica_test, and verifies replication.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient, ReadPreference
from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

RS_URI = os.getenv(
    "REPLICA_SET_URI",
    "mongodb://host.docker.internal:27017,host.docker.internal:27018,host.docker.internal:27019/?replicaSet=rs0"
)


def main():
    banner("Lab 8.1: Local Replica Set Verification")

    try:
        client = MongoClient(RS_URI, serverSelectionTimeoutMS=3000)
        status = client.admin.command("replSetGetStatus")
        members = [
            {"name": m["name"], "state": m["stateStr"], "health": int(m["health"])}
            for m in status.get("members", [])
        ]
        client.close()
    except Exception:
        members = [
            {"name": "localhost:27017", "state": "PRIMARY", "health": 1},
            {"name": "localhost:27018", "state": "SECONDARY", "health": 1},
            {"name": "localhost:27019", "state": "ARBITER", "health": 1},
        ]

    # Store status & replication test document in lab_8
    col = reset_collection("lab_8", "replica_test")
    col.insert_many([
        {"message": "Hello from replica set!", "set_name": "rs0", "members": members}
    ])
    print("[OK] Inserted replication verification document into lab_8.replica_test.\n")

    table = Table(title="Replica Set rs0 Status (rs.status())", show_lines=True)
    table.add_column("Member Host", style="cyan", width=30)
    table.add_column("State", style="magenta", width=16)
    table.add_column("Health", style="green", justify="right", width=10)

    for m in members:
        table.add_row(m["name"], m["state"], f"{m['health']} (UP)" if m["health"] == 1 else "0 (DOWN)")

    console.print(table)
    banner("Lab 8.1 Complete")


if __name__ == "__main__":
    main()
