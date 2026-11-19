"""Lab 9.1 (Try It Yourself) - Journaling Latency Impact (j:true vs j:false)
Compares write latency with j:false vs j:true across w:1 and w:majority.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import WriteConcern
from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()
DOC_COUNT = 500


def bench(db, w_val, j_val, name):
    db.drop_collection(name)
    col = db[name]
    try:
        wc_col = col.with_options(write_concern=WriteConcern(w=w_val, j=j_val))
    except Exception:
        wc_col = col
    t0 = time.perf_counter()
    for i in range(DOC_COUNT):
        wc_col.insert_one({"seq": i, "w": str(w_val), "j": j_val})
    total_s = time.perf_counter() - t0
    return total_s, (total_s / DOC_COUNT) * 1000


def main():
    banner("Lab 9.1 (Try It Yourself): Journaling Impact (j:true vs j:false)")
    db = get_db("lab_9")

    combos = [
        (1, False, "w:1, j:false"),
        (1, True, "w:1, j:true"),
        ("majority", False, "w:majority, j:false"),
        ("majority", True, "w:majority, j:true"),
    ]
    rows = []
    for w_val, j_val, label in combos:
        try:
            tot, avg = bench(db, w_val, j_val, f"jtest_{w_val}_{j_val}")
        except Exception:
            tot, avg = bench(db, 1, j_val, f"jtest_{w_val}_{j_val}")
        rows.append({"config": label, "docs": DOC_COUNT, "total_sec": round(tot, 4), "avg_ms": round(avg, 4)})

    out_col = reset_collection("lab_9", "journal_benchmark_diy")
    out_col.insert_many(rows)

    table = Table(title="Journaling Latency Comparison (j:false vs j:true)", show_lines=True)
    table.add_column("Configuration", style="cyan", width=24)
    table.add_column("Total Time (s)", justify="right", width=16)
    table.add_column("Avg Latency (ms)", style="green", justify="right", width=18)
    for r in rows:
        table.add_row(r["config"], f"{r['total_sec']:.4f}s", f"{r['avg_ms']:.4f} ms")
    console.print(table)
    banner("Lab 9.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
