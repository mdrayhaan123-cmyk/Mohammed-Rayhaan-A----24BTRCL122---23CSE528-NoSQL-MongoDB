def main():
    print("=" * 76)
    print("LAB 11.1 (Try It Yourself): MongoDB 5.0+ Online Resharding")
    print("=" * 76)

    steps = [
        "1. Create supporting index on target key: db.orders.createIndex({ customer_id: 'hashed' })",
        "2. Run adminCommand: db.adminCommand({ reshardCollection: 'ecommerce.orders', key: { customer_id: 'hashed' } })",
        "3. Clone & Oplog Tail: Recipient shards clone existing docs while applying live oplog writes.",
        "4. Critical Section & Commit: Brief write pause (~seconds) to switch routing metadata atomically.",
    ]
    print("[STEPS]")
    for s in steps:
        print(f"  {s}")

    limitations = [
        "Disk Space: Requires ~1.2x free storage headroom on recipient shards during cloning.",
        "Single Concurrency: Only one reshardCollection operation may execute cluster-wide at a time.",
        "DDL Lock: Blocks concurrent drop, renameCollection, or collMod on the target collection.",
        "Latency Spike: Brief write pause during the critical section while finalizing oplog sync.",
    ]
    print("\n[LIMITATIONS]")
    for lim in limitations:
        print(f"  - {lim}")

if __name__ == "__main__":
    main()