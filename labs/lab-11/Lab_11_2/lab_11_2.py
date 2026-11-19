import os
import time
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from connection import get_client, get_db

def extract_shards(explain_doc: dict):
    qp = explain_doc.get("queryPlanner", {}).get("winningPlan", {})
    shards = qp.get("shards", [])
    if shards:
        return [s.get("shardName") for s in shards]
    stages = explain_doc.get("executionStats", {}).get("executionStages", {})
    if "shards" in stages:
        return [s.get("shardName") for s in stages["shards"]]
    return ["standalone-or-primary"]

def print_shard_distribution(db, coll_name: str):
    stats = db.command("collStats", coll_name)
    total_count = stats.get("count", 0)
    shards_info = stats.get("shards", {})
    print(f"\n[collStats: {db.name}.{coll_name}] Total Docs = {total_count}")
    if not shards_info:
        print(f"  Single/Unsharded node count: {total_count}")
        return
    for shard_name in sorted(shards_info.keys()):
        s_count = shards_info[shard_name].get("count", 0)
        s_size_kb = shards_info[shard_name].get("size", 0) / 1024.0
        pct = (s_count / total_count * 100.0) if total_count else 0.0
        print(f"  - {shard_name:<10}: {s_count:5d} docs ({pct:5.1f}%) | Data Size: {s_size_kb:7.2f} KB")

def main():
    print("=" * 76)
    print("LAB 11.2: Shard Key Hotspot Detection & Query Targeting Comparison")
    print("=" * 76)

    client = get_client()
    db_name = os.getenv("DB_NAME", "lab_11")
    db = get_db(client)
    admin = client.admin

    client["config"].settings.update_one({"_id": "chunksize"}, {"$set": {"value": 1}}, upsert=True)
    db.hotspot_data.drop()
    db.even_data.drop()

    is_mongos = client.admin.command("hello").get("msg") == "isdbgrid"
    if is_mongos:
        admin.command("enableSharding", db_name, primaryShard="shard1rs")
        db.hotspot_data.create_index([("ts", 1)])
        db.even_data.create_index([("user_id", "hashed")])
        admin.command("shardCollection", f"{db_name}.hotspot_data", key={"ts": 1})
        admin.command("shardCollection", f"{db_name}.even_data", key={"user_id": "hashed"})

        split_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        admin.command("split", f"{db_name}.hotspot_data", middle={"ts": split_ts})
        shards = [s["_id"] for s in client["config"].shards.find({}, {"_id": 1}).sort("_id", 1)]
        if len(shards) >= 2:
            try:
                admin.command(
                    "moveChunk",
                    f"{db_name}.hotspot_data",
                    find={"ts": datetime(2023, 6, 1, tzinfo=timezone.utc)},
                    to="shard2rs",
                )
            except Exception:
                pass
        print(f"[CLUSTER] Sharding enabled on '{db_name}' across shards: {shards}")
    else:
        print("[WARN] Connected to non-mongos instance; shard distribution will reflect single node.")

    print("\n--- Inserting 10,000 documents into hotspot_data ({ts: 1}) ---")
    base_old = datetime(2023, 1, 1, tzinfo=timezone.utc)
    base_recent = datetime(2025, 1, 1, tzinfo=timezone.utc)
    payload = "X" * 240

    hotspot_docs = []
    for i in range(500):
        hotspot_docs.append({"seq": i, "ts": base_old + timedelta(minutes=i), "payload": payload})
    for i in range(9500):
        hotspot_docs.append({"seq": 500 + i, "ts": base_recent + timedelta(seconds=i * 10), "payload": payload})

    db.hotspot_data.insert_many(hotspot_docs, ordered=False)

    print("--- Inserting 10,000 documents into even_data ({user_id: 'hashed'}) ---")
    even_docs = [
        {"seq": i, "user_id": ObjectId(), "ts": base_recent + timedelta(seconds=i * 10), "payload": payload}
        for i in range(10000)
    ]
    db.even_data.insert_many(even_docs, ordered=False)
    time.sleep(1.5)

    print_shard_distribution(db, "hotspot_data")
    print_shard_distribution(db, "even_data")

    print("\n--- Range Query Targeting Comparison (explain()) ---")
    exp_hotspot = db.hotspot_data.find({
        "ts": {
            "$gte": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "$lt": datetime(2025, 12, 31, tzinfo=timezone.utc),
        }
    }).explain()
    hs_shards = extract_shards(exp_hotspot)
    hs_docs = exp_hotspot.get("executionStats", {}).get("nReturned", 0)
    print(f"  1. hotspot_data range on 'ts'     -> Targeted Shards: {hs_shards} | Returned: {hs_docs} (Targeted Single-Shard Scan)")

    mid_oid = ObjectId.from_datetime(datetime(2026, 6, 1, tzinfo=timezone.utc))
    exp_even = db.even_data.find({
        "user_id": {"$gte": ObjectId("000000000000000000000000"), "$lt": mid_oid}
    }).explain()
    ev_shards = extract_shards(exp_even)
    ev_docs = exp_even.get("executionStats", {}).get("nReturned", 0)
    print(f"  2. even_data range on 'user_id'   -> Targeted Shards: {ev_shards} | Returned: {ev_docs} (Scatter-Gather Broadcast)")

if __name__ == "__main__":
    main()