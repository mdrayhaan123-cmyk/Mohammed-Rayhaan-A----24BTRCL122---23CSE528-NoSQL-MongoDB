import time
from datetime import datetime, timezone
from tabulate import tabulate
from pymongo import ASCENDING
from connection import get_client, get_db

def main():
    print("=" * 78)
    print("LAB 15.2: Document-Level to Collection-Per-Tenant Migration & Benchmarks")
    print("=" * 78)

    client = get_client()
    db = get_db(client)

    tenants = ["acme", "globex", "initech", "umbrella", "wayne"]
    tasks_per_tenant = 100

    # Clean slate
    db.tasks_shared.drop()
    for tid in tenants:
        db[f"tasks_tenant_{tid}"].drop()

    # 1. Seed 5 tenants x 100 tasks = 500 documents in shared document-level collection
    db.tasks_shared.create_index([("tenant_id", ASCENDING), ("created_at", ASCENDING)])
    seed_docs = []
    priorities = ["low", "medium", "high"]
    statuses = ["open", "in_progress", "done"]
    for t_idx, tid in enumerate(tenants):
        for i in range(1, tasks_per_tenant + 1):
            seed_docs.append({
                "tenant_id": tid,
                "title": f"{tid.upper()} Task #{i}",
                "status": statuses[(i + t_idx) % 3],
                "priority": priorities[i % 3],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    db.tasks_shared.insert_many(seed_docs)
    print(f"[SEED] Inserted {db.tasks_shared.count_documents({})} total documents across {len(tenants)} tenants into 'tasks_shared'")

    # 2. Migrate to Collection-Per-Tenant using $match + $out aggregation
    t_mig_start = time.perf_counter()
    for tid in tenants:
        target_coll = f"tasks_tenant_{tid}"
        db.tasks_shared.aggregate([
            {"$match": {"tenant_id": tid}},
            {"$out": target_coll},
        ])
    mig_ms = round((time.perf_counter() - t_mig_start) * 1000, 2)
    print(f"[MIGRATION] Migrated 5 tenants to dedicated 'tasks_tenant_<id>' collections in {mig_ms} ms")

    # 3. Validate counts and zero cross-tenant leakage
    for tid in tenants:
        src_count = db.tasks_shared.count_documents({"tenant_id": tid})
        dst_coll = db[f"tasks_tenant_{tid}"]
        dst_count = dst_coll.count_documents({})
        leaked = dst_coll.count_documents({"tenant_id": {"$ne": tid}})
        assert src_count == dst_count == tasks_per_tenant, f"Count mismatch for {tid}"
        assert leaked == 0, f"Cross-tenant leakage detected in tasks_tenant_{tid}!"
    print("[VALIDATION] Verified 100/100 documents per tenant & 0 cross-tenant leaks across all 5 collections")

    # 4. Benchmark Query Performance (Document-Level vs Collection-Per-Tenant)
    iterations = 50

    # 4a. Single-Tenant List Query
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = list(db.tasks_shared.find({"tenant_id": "acme"}))
    doc_list_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = list(db.tasks_tenant_acme.find({}))
    coll_list_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    # 4b. Single-Tenant Task Insert
    t0 = time.perf_counter()
    for i in range(iterations):
        db.tasks_shared.insert_one({"tenant_id": "acme", "title": f"Bench Doc {i}", "status": "open", "priority": "low", "created_at": datetime.now(timezone.utc).isoformat()})
    doc_ins_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    t0 = time.perf_counter()
    for i in range(iterations):
        db.tasks_tenant_acme.insert_one({"tenant_id": "acme", "title": f"Bench Coll {i}", "status": "open", "priority": "low", "created_at": datetime.now(timezone.utc).isoformat()})
    coll_ins_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    # 4c. Cross-Tenant Analytics (Count tasks per tenant & status)
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = list(db.tasks_shared.aggregate([
            {"$group": {"_id": {"tenant": "$tenant_id", "status": "$status"}, "count": {"$sum": 1}}}
        ]))
    doc_agg_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    union_stages = [{"$unionWith": {"coll": f"tasks_tenant_{tid}"}} for tid in tenants[1:]]
    union_stages.append({"$group": {"_id": {"tenant": "$tenant_id", "status": "$status"}, "count": {"$sum": 1}}})
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = list(db[f"tasks_tenant_{tenants[0]}"].aggregate(union_stages))
    coll_agg_ms = round(((time.perf_counter() - t0) / iterations) * 1000, 3)

    bench_rows = [
        ["List Single-Tenant Tasks", f"{doc_list_ms} ms", f"{coll_list_ms} ms", "Collection-Per-Tenant (no tenant_id index filter)"],
        ["Insert Single Task", f"{doc_ins_ms} ms", f"{coll_ins_ms} ms", "Collection-Per-Tenant (smaller per-tenant B-tree)"],
        ["Cross-Tenant Analytics", f"{doc_agg_ms} ms", f"{coll_agg_ms} ms", "Document-Level (single $group vs 5-way $unionWith)"],
    ]
    print("\n--- Query Performance Comparison (Avg over 50 iterations) ---")
    print(tabulate(bench_rows, headers=["Workload", "Document-Level", "Collection-Per-Tenant", "Faster Strategy & Reason"], tablefmt="grid"))

    # Persist benchmark results in lab_15.isolation_benchmarks for Compass inspection
    db.isolation_benchmarks.drop()
    db.isolation_benchmarks.insert_many([
        {
            "workload": r[0],
            "document_level_ms": r[1],
            "collection_per_tenant_ms": r[2],
            "winner": r[3],
        }
        for r in bench_rows
    ])

    print("\n--- Architectural Recommendation ---")
    print("  1. Document-Level Isolation   : Best for high tenant counts (1,000s+), frequent cross-tenant analytics, and uniform schema evolution.")
    print("  2. Collection-Per-Tenant      : Best when strict regulatory separation, independent per-tenant backup/restore, or custom per-tenant indexes are required.")

if __name__ == "__main__":
    main()