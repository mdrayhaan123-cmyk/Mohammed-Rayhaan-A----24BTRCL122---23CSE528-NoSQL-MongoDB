"""Lab 7.2 - Working Set Analysis
Insert 100K ~2KB documents into lab_7.working_set_docs, inspect WiredTiger cache,
and run random reads to evaluate cache hit ratio.
"""

import sys, os, time, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner


def main():
    banner("Lab 7.2: Working Set Analysis")
    db = get_db("lab_7")
    col = reset_collection("lab_7", "working_set_docs")

    count = 100000
    print(f"Inserting {count:,} documents (~2KB each)...")
    docs = [{"doc_id": f"DOC-{i:06d}", "reading": i * 0.01, "payload": "x" * 1800} for i in range(count)]
    start = time.perf_counter()
    col.insert_many(docs)
    elapsed = time.perf_counter() - start
    print(f"[OK] Inserted {count:,} docs in {elapsed:.2f}s ({count/elapsed:,.0f} docs/sec)")

    status = db.command("serverStatus")
    cache = status.get("wiredTiger", {}).get("cache", {})
    max_bytes = cache.get("maximum bytes configured", 0)
    used_bytes = cache.get("bytes currently in the cache", 0)

    print("\n=== WiredTiger Cache Metrics ===")
    print(f"  Cache max:          {max_bytes:>15,} bytes")
    print(f"  Cache in use:       {used_bytes:>15,} bytes")
    if max_bytes:
        print(f"  Cache utilization:  {(used_bytes / max_bytes) * 100:>14.2f}%")

    print("\n=== Random Reads Across Working Set ===")
    for _ in range(5):
        target = f"DOC-{random.randint(0, count - 1):06d}"
        t0 = time.perf_counter()
        col.find_one({"doc_id": target})
        print(f"  Read {target}: {(time.perf_counter() - t0)*1000:.2f} ms")

    cache_after = db.command("serverStatus").get("wiredTiger", {}).get("cache", {})
    pages_read = cache_after.get("pages read into cache", 0)
    pages_evict = cache_after.get("eviction pages evicted by application threads", 0)
    if pages_read > 0:
        hit_ratio = max(0.0, 1.0 - (pages_evict / pages_read))
        print(f"\n  Approx cache hit ratio: {hit_ratio:.1%}")
    banner("Lab 7.2 Complete")


if __name__ == "__main__":
    main()
