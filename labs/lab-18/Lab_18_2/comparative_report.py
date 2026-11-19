from tabulate import tabulate
from connection import get_mongo_client, get_db

def main():
    print("=" * 78)
    print("LAB 18.2: Comparative Analysis, Horizontal Scaling (1M/10M/100M) & Ops")
    print("=" * 78)

    client = get_mongo_client()
    db = get_db(client)

    print("\n(1) Executive Summary:")
    print("  For threat intelligence false-positive triage, a hybrid architecture—MongoDB for rich threat")
    print("  documents & recent-threat views, Cassandra for high-ingest time-series/source partitions, and Neo4j")
    print("  for SUSPICIOUS false-positive graph clustering—outperforms any single engine across all access patterns.")

    scale_rows = [
        ["1M Records (~1.2 GB)", "1 shard (3-node RS)", "3-node ring (RF=2)", "1 single-instance / small cluster", "8 GB RAM / 20 GB NVMe"],
        ["10M Records (~12 GB)", "2-3 shards (hashed/ranged)", "3-5 nodes (RF=3)", "Cluster (4-8 GB heap)", "32 GB RAM / 100 GB NVMe"],
        ["100M Records (~120 GB)", "6-8 shards + config RS", "6-12 nodes (RF=3)", "Causal cluster / sharded graph", "128 GB RAM / 500+ GB NVMe"],
    ]
    print("\n--- Horizontal Scaling & Hardware Estimates (1M | 10M | 100M Records) ---")
    print(tabulate(
        scale_rows,
        headers=["Scale & Raw Footprint", "MongoDB Sharding", "Cassandra Topology", "Neo4j Scaling", "Est. Node Spec"],
        tablefmt="grid",
    ))

    rec_rows = [
        ["Threat History & Rich IOC Payloads", "MongoDB", "Compound index (from_source, timestamp) + embedded recent_threats[50]"],
        ["Real-Time Burst Ingest & Partition Scans", "Cassandra", "Leaderless tunable consistency writes & single-partition lookups"],
        ["False-Positive Rings & Co-Occurrence", "Neo4j", "Index-free adjacency traversal across SUSPICIOUS edges"],
        ["Aggregated Daily Volume Analytics", "MongoDB / Cassandra", "Pre-aggregated (threat_type, day) partitions or indexed $group pipelines"],
    ]
    print("\n--- Access-Pattern Recommendations ---")
    print(tabulate(rec_rows, headers=["Access Pattern", "Recommended DB", "Rationale"], tablefmt="grid"))

    db.comparative_report.drop()
    db.comparative_report.insert_one({
        "scale_estimates": [
            {"scale": r[0], "mongodb": r[1], "cassandra": r[2], "neo4j": r[3], "hardware": r[4]}
            for r in scale_rows
        ],
        "recommendations": [
            {"pattern": r[0], "database": r[1], "rationale": r[2]}
            for r in rec_rows
        ],
    })
    print("[SAVED] Stored Lab 18.2 comparative analysis into 'lab_18.comparative_report'")

if __name__ == "__main__":
    main()