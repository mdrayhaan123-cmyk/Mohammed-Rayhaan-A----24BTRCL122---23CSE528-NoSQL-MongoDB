"""Lab 4.1 (Try It Yourself) - Case-Insensitive $regex Product Search

Extends the Lab 4.1 Product Query API with case-insensitive $regex text search
across product names, storing results in lab_4.products_diy.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()

PRODUCTS = [
    {"sku": "LAP-001", "name": "ProBook 15", "category": "Laptops", "price": 899.99,
     "brand": "TechCorp", "stock": 45, "tags": ["business", "15-inch"], "rating": 4.5, "active": True},
    {"sku": "LAP-002", "name": "UltraBook 14", "category": "Laptops", "price": 1299.99,
     "brand": "TechCorp", "stock": 12, "tags": ["premium", "14-inch", "lightweight"], "rating": 4.8, "active": True},
    {"sku": "MON-001", "name": "WideView 27", "category": "Monitors", "price": 449.99,
     "brand": "DisplayPlus", "stock": 30, "tags": ["4K", "27-inch", "USB-C"], "rating": 4.3, "active": True},
    {"sku": "MON-002", "name": "GamePanel 32", "category": "Monitors", "price": 699.99,
     "brand": "DisplayPlus", "stock": 8, "tags": ["gaming", "32-inch", "144Hz"], "rating": 4.7, "active": True},
    {"sku": "KBD-001", "name": "TypeMaster Pro", "category": "Keyboards", "price": 149.99,
     "brand": "KeyTech", "stock": 100, "tags": ["mechanical", "wireless", "backlit"], "rating": 4.6, "active": True},
    {"sku": "KBD-002", "name": "SilentType 60", "category": "Keyboards", "price": 89.99,
     "brand": "KeyTech", "stock": 0, "tags": ["mechanical", "60-percent", "silent"], "rating": 4.4, "active": False},
    {"sku": "LAP-003", "name": "BudgetBook 15", "category": "Laptops", "price": 549.99,
     "brand": "ValueTech", "stock": 0, "tags": ["budget", "15-inch"], "rating": 3.9, "active": False},
]


def search_by_name_regex(col, search_text: str):
    """Find products whose name contains search_text (case-insensitive)."""
    return list(col.find(
        {"name": {"$regex": search_text, "$options": "i"}},
        {"sku": 1, "name": 1, "category": 1, "price": 1, "stock": 1, "_id": 0}
    ))


def main():
    banner("Lab 4.1 (Try It Yourself): Case-Insensitive $regex Search")
    col = reset_collection("lab_4", "products_diy")
    col.insert_many(PRODUCTS)
    print(f"[OK] Inserted {len(PRODUCTS)} products into lab_4.products_diy.\n")

    for term in ["book", "pro", "60"]:
        matches = search_by_name_regex(col, term)
        table = Table(title=f"$regex Search: '{term}' (case-insensitive)", show_lines=True)
        table.add_column("SKU", style="cyan", width=10)
        table.add_column("Name", style="green", width=20)
        table.add_column("Category", width=12)
        table.add_column("Price", style="magenta", width=12)
        table.add_column("Stock", width=8)

        for m in matches:
            table.add_row(m["sku"], m["name"], m["category"], f"${m['price']:.2f}", str(m["stock"]))
        console.print(table)
        print()

    banner("Lab 4.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
