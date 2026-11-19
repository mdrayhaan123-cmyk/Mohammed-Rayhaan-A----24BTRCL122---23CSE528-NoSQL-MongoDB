"""Lab 9.2 - Network Partition Simulation & Timeline Logger

Models and logs the 3-node replica set behavior during:
  1. Baseline healthy quorum (3/3)
  2. 1 secondary partitioned (2/3 majority -> w:1 & w:majority succeed)
  3. 2nd secondary partitioned (1/3 no majority -> w:majority times out, primary steps down)
  4. Partition healed (3/3 -> election & catch-up)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

PARTITION_TIMELINE = [
    {"phase": "T+00s: Baseline Healthy", "online_nodes": "3/3", "w1_result": "SUCCEEDS", "wmaj_result": "SUCCEEDS", "primary_state": "PRIMARY"},
    {"phase": "T+10s: Disconnect 1 Secondary", "online_nodes": "2/3 (Majority)", "w1_result": "SUCCEEDS", "wmaj_result": "SUCCEEDS", "primary_state": "PRIMARY"},
    {"phase": "T+25s: Disconnect 2nd Secondary", "online_nodes": "1/3 (No Majority)", "w1_result": "FAILS (Read-Only)", "wmaj_result": "TIMEOUT", "primary_state": "STEPPED DOWN -> SECONDARY"},
    {"phase": "T+40s: Reconnect Both Nodes", "online_nodes": "3/3 (Healed)", "w1_result": "SUCCEEDS", "wmaj_result": "SUCCEEDS", "primary_state": "PRIMARY (Re-elected)"},
]


def main():
    banner("Lab 9.2: Network Partition Simulation")
    col = reset_collection("lab_9", "partition_events")
    col.insert_many(PARTITION_TIMELINE)

    table = Table(title="Network Partition Behavior Timeline (lab_9.partition_events)", show_lines=True)
    table.add_column("Timeline Phase", style="cyan", width=30)
    table.add_column("Quorum", width=18)
    table.add_column("w:1 Write", style="green", width=18)
    table.add_column("w:majority Write", style="magenta", width=16)
    table.add_column("Primary State", width=26)

    for row in col.find({}):
        table.add_row(row["phase"], row["online_nodes"], row["w1_result"], row["wmaj_result"], row["primary_state"])

    console.print(table)
    banner("Lab 9.2 Complete")


if __name__ == "__main__":
    main()
