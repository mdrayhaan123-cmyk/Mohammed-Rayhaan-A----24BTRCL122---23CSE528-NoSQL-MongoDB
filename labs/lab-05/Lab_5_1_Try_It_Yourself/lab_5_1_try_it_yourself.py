"""Lab 5.1 (Try It Yourself) - $bucket Order Value Categorization

Uses MongoDB's $bucket stage to categorize orders into:
  - Small  (under $50)
  - Medium ($50 - $200)
  - Large  (over $200)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

ORDERS_DIY = [
    {"order_id": "ORD-301", "customer": "Arjun", "total": 18.50, "status": "completed"},
    {"order_id": "ORD-302", "customer": "Sneha", "total": 34.99, "status": "completed"},
    {"order_id": "ORD-303", "customer": "Rahul", "total": 45.00, "status": "completed"},
    {"order_id": "ORD-304", "customer": "Kavya", "total": 75.00, "status": "completed"},
    {"order_id": "ORD-305", "customer": "Divya", "total": 120.50, "status": "completed"},
    {"order_id": "ORD-306", "customer": "Arjun", "total": 185.00, "status": "completed"},
    {"order_id": "ORD-307", "customer": "Sneha", "total": 260.00, "status": "completed"},
    {"order_id": "ORD-308", "customer": "Rahul", "total": 450.00, "status": "completed"},
    {"order_id": "ORD-309", "customer": "Vikram", "total": 890.00, "status": "completed"},
]


def main():
    banner("Lab 5.1 (Try It Yourself): $bucket Order Categorization")
    col = reset_collection("lab_5", "orders_diy")
    col.insert_many(ORDERS_DIY)
    print(f"[OK] Inserted {len(ORDERS_DIY)} orders into lab_5.orders_diy.\n")

    pipeline = [
        {
            "$bucket": {
                "groupBy": "$total",
                "boundaries": [0, 50, 200],
                "default": "Large (Over $200)",
                "output": {
                    "order_count": {"$sum": 1},
                    "total_revenue": {"$sum": "$total"},
                    "order_ids": {"$push": "$order_id"},
                },
            }
        }
    ]

    label_map = {
        0: "Small (Under $50)",
        50: "Medium ($50 - $200)",
        "Large (Over $200)": "Large (Over $200)",
    }

    table = Table(title="Order Value Buckets ($bucket Stage)", show_lines=True)
    table.add_column("Category", style="cyan", width=22)
    table.add_column("Orders", style="magenta", justify="right", width=8)
    table.add_column("Total Revenue", style="green", justify="right", width=15)
    table.add_column("Order IDs", width=36)

    for row in col.aggregate(pipeline):
        label = label_map.get(row["_id"], str(row["_id"]))
        table.add_row(
            label,
            str(row["order_count"]),
            f"${row['total_revenue']:,.2f}",
            ", ".join(row["order_ids"]),
        )

    console.print(table)
    banner("Lab 5.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
