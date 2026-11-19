"""Lab 6.1 (Try It Yourself) - Measure Index Usage with $indexStats

Creates 3 indexes on lab_6.server_logs_diy, runs representative queries
multiple times, and uses $indexStats to identify the most frequently used index.
"""

import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()


def generate_logs(count=5000):
    levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    services = ["auth-svc", "payment-svc", "inventory-svc", "api-gateway"]
    return [
        {
            "level": random.choice(levels),
            "service": random.choice(services),
            "response_time_ms": random.randint(1, 5000),
            "status_code": random.choice([200, 201, 400, 404, 500]),
        }
        for _ in range(count)
    ]


def main():
    banner("Lab 6.1 (Try It Yourself): $indexStats Usage Analysis")
    col = reset_collection("lab_6", "server_logs_diy")
    col.insert_many(generate_logs(5000))
    print(f"[OK] Inserted {col.count_documents({})} log entries into lab_6.server_logs_diy.\n")

    # Create 3 indexes
    col.create_index([("level", 1), ("service", 1)], name="idx_level_service")
    col.create_index([("service", 1), ("response_time_ms", -1)], name="idx_service_latency")
    col.create_index([("status_code", 1)], name="idx_status")

    # Execute workload multiple times
    for _ in range(50):
        list(col.find({"level": "ERROR", "service": "payment-svc"}).limit(5))
    for _ in range(20):
        list(col.find({"service": "api-gateway", "response_time_ms": {"$gt": 3000}}).limit(5))
    for _ in range(5):
        list(col.find({"status_code": 404}).limit(5))

    print("[OK] Executed query workload (50x ERROR+service, 20x slow gateway, 5x 404).\n")

    # Aggregate with $indexStats
    stats = list(col.aggregate([{"$indexStats": {}}]))
    stats.sort(key=lambda s: s["accesses"]["ops"], reverse=True)

    table = Table(title="MongoDB $indexStats Usage Report", show_lines=True)
    table.add_column("Index Name", style="cyan", width=24)
    table.add_column("Key Pattern", width=36)
    table.add_column("Accesses (ops)", style="green", justify="right", width=16)

    for s in stats:
        table.add_row(s["name"], str(s["key"]), str(s["accesses"]["ops"]))

    console.print(table)
    most_used = stats[0]
    print(f"\n  Most frequently used index: {most_used['name']} ({most_used['accesses']['ops']} ops)")

    banner("Lab 6.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
