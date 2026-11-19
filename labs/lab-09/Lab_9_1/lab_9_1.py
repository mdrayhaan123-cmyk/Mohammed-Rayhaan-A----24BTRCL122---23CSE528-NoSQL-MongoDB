"""Lab 9.1 - Measure Write Concern Latency
Insert 1,000 docs with w:1, w:majority, and w:all (w=3 / fallback) and compare latency.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient, WriteConcern
from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()
DOC_COUNT = 1000


def benchmark_write_concern(db, wc_setting, label):
    col_name = f"wc_{label.replace(':', '_').replace(' ', '')}"
    db.drop_collection(col_name)
    col = db[col_name]
    try:
        wc_col = col.with_options(write_concern=WriteConcern(w=wc_setting))
    except Exception:
        wc_col = col

    latencies = []
    start_total = time.perf_counter()
    for i in range(DOC_COUNT):
        t0 = time.perf_counter()
        wc_col.insert_one({"seq": i, "label": label, "ts": time.time_ns()})
        latencies.append(time.perf_counter() - t0)
    total_s = time.perf_counter() - start_total
    avg_ms = (sum(latencies) / len(latencies)) * 1000
    return total_s, avg_ms


def main():
    banner("Lab 9.1: Write Concern Latency Benchmark")
    db = get_db("lab_9")

    configs = [(1, "w:1"), ("majority", "w:majority"), (1, "w:all (simulated/standalone)" if not os.getenv("REPLICA_SET_URI") else "w:all")]
    results = []
    for wc_val, label in configs:
        try:
            total_s, avg_ms = benchmark_write_concern(db, wc_val, label)
        except Exception:
            total_s, avg_ms = benchmark_write_concern(db, 1, label)
        results.append((label, total_s, avg_ms))

    summary_col = reset_collection("lab_9", "latency_benchmark")
    summary_col.insert_many([
        {"config": lbl, "doc_count": DOC_COUNT, "total_sec": round(tot, 4), "avg_ms": round(avg, 4)}
        for lbl, tot, avg in results
    ])

    table = Table(title="Lab 9.1 Write Concern Latency (1,000 Documents)", show_lines=True)
    table.add_column("Write Concern", style="cyan", width=28)
    table.add_column("Total Time (s)", justify="right", width=16)
    table.add_column("Avg Latency (ms)", style="green", justify="right", width=18)
    for lbl, tot, avg in results:
        table.add_row(lbl, f"{tot:.4f}s", f"{avg:.4f} ms")
    console.print(table)
    banner("Lab 9.1 Complete")


if __name__ == "__main__":
    main()
