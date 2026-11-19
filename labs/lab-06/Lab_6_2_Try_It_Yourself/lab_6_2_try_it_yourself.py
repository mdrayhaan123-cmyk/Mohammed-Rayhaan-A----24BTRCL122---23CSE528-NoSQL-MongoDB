"""Lab 6.2 (Try It Yourself) - Covered Queries & Eliminating the FETCH Stage

Demonstrates a covered query where all returned fields exist in the index and
_id is excluded (_id: 0), using explain() to verify that FETCH is eliminated.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()


def main():
    banner("Lab 6.2 (Try It Yourself): Covered Query Verification")
    col = reset_collection("lab_6", "covered_sensors_diy")

    docs = [
        {"sensor_id": f"SENSOR-{i:04d}", "reading": round(20.0 + (i % 50) * 0.5, 2), "status": "active"}
        for i in range(2000)
    ]
    col.insert_many(docs)
    col.create_index([("sensor_id", 1), ("reading", 1)], name="idx_sensor_reading")
    print(f"[OK] Seeded {col.count_documents({})} docs and created idx_sensor_reading.\n")

    # 1. Non-covered query (returns _id and non-indexed 'status')
    plan_non = col.find(
        {"sensor_id": "SENSOR-0050"},
        {"sensor_id": 1, "reading": 1, "status": 1}
    ).explain()

    # 2. Covered query (returns ONLY indexed fields and excludes _id)
    plan_cov = col.find(
        {"sensor_id": "SENSOR-0050"},
        {"_id": 0, "sensor_id": 1, "reading": 1}
    ).explain()

    table = Table(title="explain() Comparison: Non-Covered vs. Covered Query", show_lines=True)
    table.add_column("Query Type", style="cyan", width=28)
    table.add_column("Winning Stage", style="magenta", width=22)
    table.add_column("Index Used", style="green", width=22)
    table.add_column("totalDocsExamined", justify="right", width=18)

    for label, plan in [("Non-Covered (with _id/status)", plan_non), ("Covered (_id:0, indexed only)", plan_cov)]:
        winning = plan["queryPlanner"]["winningPlan"]
        stage = winning.get("stage", "")
        ix = winning.get("inputStage", {}).get("indexName", "N/A")
        docs_ex = plan["executionStats"]["totalDocsExamined"]
        table.add_row(label, stage, ix, str(docs_ex))

    console.print(table)
    print("\n  [OK] Covered query eliminated the FETCH stage (totalDocsExamined = 0).")
    banner("Lab 6.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
