"""Lab 2.2 (Try It Yourself) - Update Books Published Before 2010 by 10%

Seeds the lab_2.books_diy collection, applies a targeted 10% price increase
only to books published before 2010 ($lt: 2010), and verifies the updated prices.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.console import Console
from rich.table import Table

console = Console()

BOOKS = [
    {"title": "The Pragmatic Programmer", "author": "David Thomas & Andrew Hunt",
     "year": 2019, "genre": "Software Engineering", "price": 49.99, "isbn": "978-0135957059",
     "tags": ["programming", "career", "best-practices"],
     "publisher": {"name": "Addison-Wesley", "location": "Boston"}},
    {"title": "Designing Data-Intensive Applications", "author": "Martin Kleppmann",
     "year": 2017, "genre": "Databases", "price": 45.99, "isbn": "978-1449373320",
     "tags": ["databases", "distributed-systems", "architecture"],
     "publisher": {"name": "O'Reilly Media", "location": "Sebastopol"}},
    {"title": "Deep Learning", "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
     "year": 2016, "genre": "Machine Learning", "price": 72.00, "isbn": "978-0262035613",
     "tags": ["AI", "neural-networks", "theory"],
     "publisher": {"name": "MIT Press", "location": "Cambridge"}},
    {"title": "Clean Code", "author": "Robert C. Martin",
     "year": 2008, "genre": "Software Engineering", "price": 39.99, "isbn": "978-0132350884",
     "tags": ["programming", "clean-code", "refactoring"],
     "publisher": {"name": "Prentice Hall", "location": "Upper Saddle River"}},
    {"title": "Hands-On Machine Learning", "author": "Aurelien Geron",
     "year": 2022, "genre": "Machine Learning", "price": 59.99, "isbn": "978-1098125974",
     "tags": ["AI", "scikit-learn", "tensorflow", "practical"],
     "publisher": {"name": "O'Reilly Media", "location": "Sebastopol"}},
    {"title": "Refactoring (1st Edition)", "author": "Martin Fowler",
     "year": 1999, "genre": "Software Engineering", "price": 44.00, "isbn": "978-0201485677",
     "tags": ["programming", "refactoring", "object-oriented"],
     "publisher": {"name": "Addison-Wesley", "location": "Boston"}},
]


def main():
    banner("Lab 2.2 (Try It Yourself): 10% Price Increase for Pre-2010 Books")
    db = get_db("lab_2")
    col = reset_collection("lab_2", "books_diy")

    # Seed initial books
    result = col.insert_many(BOOKS)
    print(f"[OK] Inserted {len(result.inserted_ids)} books into lab_2.books_diy\n")

    # Capture prices before update
    before = {b["title"]: (b["year"], b["price"]) for b in col.find({}, {"title": 1, "year": 1, "price": 1, "_id": 0})}

    # Targeted update: increase price by 10% ONLY for books published before 2010
    update_result = col.update_many({"year": {"$lt": 2010}}, {"$mul": {"price": 1.10}})
    print(f"[OK] Updated {update_result.modified_count} book(s) published before 2010.\n")

    # Capture prices after update and render comparison table
    after = {b["title"]: b["price"] for b in col.find({}, {"title": 1, "price": 1, "_id": 0})}

    table = Table(title="Bookstore Price Update Verification (Pre-2010 +10%)", show_lines=True)
    table.add_column("Title", style="cyan", width=40)
    table.add_column("Year", style="magenta", width=6)
    table.add_column("Old Price", width=12)
    table.add_column("New Price", style="green", width=12)
    table.add_column("Status", width=18)

    for title, (year, old_price) in before.items():
        new_price = after[title]
        status = "Updated (+10%)" if year < 2010 else "Unchanged"
        table.add_row(title, str(year), f"${old_price:.2f}", f"${new_price:.2f}", status)

    console.print(table)
    print("\n[INFO] Verify in MongoDB Compass: database 'lab_2', collection 'books_diy'.")

    banner("Lab 2.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
