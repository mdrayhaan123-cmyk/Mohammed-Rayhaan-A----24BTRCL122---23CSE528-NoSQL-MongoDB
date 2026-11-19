"""Lab 3.2 (Try It Yourself) - Handling 10,000+ Comments (Subset + Referenced Pattern)

Demonstrates why embedding 10,000 comments inside a single post document is
problematic (16 MB BSON limit, unbounded growth, write amplification) and
implements the Subset + Referenced hybrid pattern.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.console import Console
from rich.table import Table

console = Console()


def main():
    banner("Lab 3.2 (Try It Yourself): 10,000 Comments Architecture")

    posts_hybrid = reset_collection("lab_3", "posts_outlier_pattern")
    comments_archive = reset_collection("lab_3", "comments_archive")

    # Insert viral post using Subset + Referenced Pattern:
    # Only the 3 most recent comments are embedded for fast initial page render,
    # while total_comments tracks the full 10,000 count.
    post_res = posts_hybrid.insert_one({
        "title": "Scaling MongoDB to Millions of Users",
        "author": "arjun",
        "total_comments": 10000,
        "recent_comments": [
            {"author": "reader9998", "text": "Great breakdown of the Subset pattern!"},
            {"author": "reader9999", "text": "How do you paginate the remaining comments?"},
            {"author": "reader10000", "text": "Using a compound index on (post_id, created_at) works well."},
        ],
    })
    post_id = post_res.inserted_id

    # Store full comment stream in separate collection (sample of archived comments)
    archived_sample = [
        {"post_id": post_id, "seq": i, "author": f"reader{i}", "text": f"Archived comment #{i}"}
        for i in range(1, 6)
    ]
    comments_archive.insert_many(archived_sample)

    print("[OK] Created hybrid post (3 embedded preview comments + 10,000 total_comments).")
    print(f"[OK] Stored paginated comment archive sample ({comments_archive.count_documents({})} docs shown).\n")

    # Comparison table: Pure Embedding vs Subset + Referenced Pattern
    table = Table(title="Design Comparison for 10,000-Comment Post", show_lines=True)
    table.add_column("Metric / Risk", style="cyan", width=26)
    table.add_column("Pure Embedding (10,000 docs)", style="red", width=36)
    table.add_column("Subset + Referenced Pattern", style="green", width=38)

    rows = [
        ("16 MB BSON Limit", "High risk of hitting/exceeding 16 MB", "Safe: post stays small (~2 KB)"),
        ("Unbounded Array Growth", "Every comment rewrites/grows parent doc", "Bounded: only top N cached in parent"),
        ("Initial Page Load", "Loads all 10,000 comments into RAM", "1 fast find() shows post + top 3 comments"),
        ("Pagination Support", "Awkward $slice on huge arrays", "Clean indexed range queries on comments"),
        ("Write Contention", "All writes contend on 1 post document", "Inserts go independently to comments"),
    ]
    for metric, bad, good in rows:
        table.add_row(metric, bad, good)

    console.print(table)
    banner("Lab 3.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
