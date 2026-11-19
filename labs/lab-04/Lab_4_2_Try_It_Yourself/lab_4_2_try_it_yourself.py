"""Lab 4.2 (Try It Yourself) - Idempotent Bulk Import via Upsert

Demonstrates an idempotent bulk_write import function using UpdateOne with
upsert=True and $set so running the import multiple times creates zero duplicates.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import UpdateOne
from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

BATCH_1 = [
    {"sku": "WGT-001", "name": "SmartWatch Pro", "price": 279.99, "stock": 45, "active": True},
    {"sku": "WGT-002", "name": "FitBand Lite", "price": 44.99, "stock": 200, "active": True},
    {"sku": "WGT-003", "name": "SmartRing X", "price": 199.99, "stock": 100, "active": True},
]

BATCH_2_WITH_OVERLAP = [
    {"sku": "WGT-002", "name": "FitBand Lite", "price": 44.99, "stock": 200, "active": True},
    {"sku": "WGT-003", "name": "SmartRing X", "price": 199.99, "stock": 100, "active": True},
    {"sku": "WGT-004", "name": "EarBuds Ultra", "price": 79.99, "stock": 150, "active": True},
    {"sku": "WGT-005", "name": "SleepTracker Mini", "price": 129.99, "stock": 80, "active": True},
]


def idempotent_bulk_import(col, docs: list[dict]):
    """Upsert each document by SKU so repeated runs never create duplicates."""
    ops = [
        UpdateOne({"sku": doc["sku"]}, {"$set": doc}, upsert=True)
        for doc in docs
    ]
    return col.bulk_write(ops)


def main():
    banner("Lab 4.2 (Try It Yourself): Idempotent Bulk Import")
    col = reset_collection("lab_4", "inventory_diy")

    runs = [
        ("Run 1 (Initial Batch 1)", BATCH_1),
        ("Run 2 (Repeat Batch 1 - Idempotent)", BATCH_1),
        ("Run 3 (Overlapping Batch 2)", BATCH_2_WITH_OVERLAP),
    ]

    for label, batch in runs:
        res = idempotent_bulk_import(col, batch)
        total = col.count_documents({})
        print(f"=== {label} ===")
        print(f"  matched={res.matched_count}, modified={res.modified_count}, upserted={res.upserted_count}, total_docs={total}\n")

    table = Table(title="Final Idempotent Inventory (lab_4.inventory_diy)", show_lines=True)
    table.add_column("SKU", style="cyan", width=10)
    table.add_column("Name", style="green", width=22)
    table.add_column("Price", style="magenta", width=10)
    table.add_column("Stock", width=8)
    table.add_column("Active", width=8)

    for doc in col.find({}, {"_id": 0}).sort("sku"):
        table.add_row(doc["sku"], doc["name"], f"${doc['price']:.2f}", str(doc["stock"]), str(doc["active"]))

    console.print(table)
    banner("Lab 4.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
