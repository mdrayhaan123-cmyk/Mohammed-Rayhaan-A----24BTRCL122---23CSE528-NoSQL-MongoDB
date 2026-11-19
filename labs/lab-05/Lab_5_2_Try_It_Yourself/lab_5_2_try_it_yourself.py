"""Lab 5.2 (Try It Yourself) - $lookup with Pipeline Sub-Expression

Uses MongoDB 3.6+ $lookup with 'let' and 'pipeline' to filter joined foreign
documents (completed orders >= $200) on the foreign side before returning them.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

CUSTOMERS = [
    {"customer_id": "C001", "name": "Arjun", "tier": "Gold"},
    {"customer_id": "C002", "name": "Sneha", "tier": "Silver"},
    {"customer_id": "C003", "name": "Rahul", "tier": "Platinum"},
]

ORDERS = [
    {"order_id": "ORD-401", "customer_id": "C001", "total": 450, "status": "completed"},
    {"order_id": "ORD-402", "customer_id": "C001", "total": 90, "status": "completed"},
    {"order_id": "ORD-403", "customer_id": "C002", "total": 310, "status": "cancelled"},
    {"order_id": "ORD-404", "customer_id": "C002", "total": 220, "status": "completed"},
    {"order_id": "ORD-405", "customer_id": "C003", "total": 780, "status": "completed"},
    {"order_id": "ORD-406", "customer_id": "C003", "total": 120, "status": "pending"},
]


def main():
    banner("Lab 5.2 (Try It Yourself): $lookup Pipeline Sub-Expression")
    customers_col = reset_collection("lab_5", "customers_diy")
    orders_col = reset_collection("lab_5", "orders_diy_lookup")

    customers_col.insert_many(CUSTOMERS)
    orders_col.insert_many(ORDERS)
    print(f"[OK] Seeded {len(CUSTOMERS)} customers and {len(ORDERS)} orders in lab_5.\n")

    # $lookup with pipeline sub-expression: filter BEFORE joining
    pipeline = [
        {
            "$lookup": {
                "from": "orders_diy_lookup",
                "let": {"cid": "$customer_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$customer_id", "$$cid"]},
                                    {"$eq": ["$status", "completed"]},
                                    {"$gte": ["$total", 200]},
                                ]
                            }
                        }
                    },
                    {"$project": {"_id": 0, "order_id": 1, "total": 1}},
                ],
                "as": "high_value_completed_orders",
            }
        }
    ]

    table = Table(title="Customers + Filtered High-Value Completed Orders (>=$200)", show_lines=True)
    table.add_column("Customer ID", style="cyan", width=12)
    table.add_column("Name", style="green", width=14)
    table.add_column("Tier", style="magenta", width=12)
    table.add_column("Matched Orders (Filtered on Foreign Side)", width=48)

    for row in customers_col.aggregate(pipeline):
        matched = ", ".join(
            f"{o['order_id']} (${o['total']})" for o in row["high_value_completed_orders"]
        ) or "None"
        table.add_row(row["customer_id"], row["name"], row["tier"], matched)

    console.print(table)
    banner("Lab 5.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
