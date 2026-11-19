"""Lab 1.2 (Try It Yourself) - Map New Real-World Applications to NoSQL Families

Maps data domains of an E-Commerce Platform and an IoT Smart Home Platform
to appropriate NoSQL database families, stores mappings in MongoDB, and summarizes usage.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.table import Table
from rich.console import Console

console = Console()


def main():
    banner("Lab 1.2 (Try It Yourself): E-Commerce & IoT Smart Home Mapping")

    db = get_db("lab_1")
    col = reset_collection("lab_1", "app_domain_mapping_diy")

    # --- E-Commerce Platform ---
    print("=== E-Commerce Platform ===")
    ecommerce_domains = [
        {
            "app": "E-Commerce Platform",
            "domain": "product_catalog",
            "description": "Diverse product SKUs with varying attributes (size, color, specs, reviews)",
            "read_write_pattern": "Read-heavy, faceted filtering, occasional updates",
            "recommended_family": "Document",
            "recommended_db": "MongoDB",
            "rationale": "Polymorphic product schemas fit naturally into flexible JSON/BSON documents"
        },
        {
            "app": "E-Commerce Platform",
            "domain": "shopping_cart",
            "description": "Active user cart items and temporary session state",
            "read_write_pattern": "Low-latency read/write, TTL expiry for abandoned carts",
            "recommended_family": "Key-Value",
            "recommended_db": "Redis",
            "rationale": "Sub-millisecond in-memory access and native key expiration"
        },
        {
            "app": "E-Commerce Platform",
            "domain": "product_search",
            "description": "Full-text keyword search, autocomplete, and relevance ranking",
            "read_write_pattern": "Search-heavy, inverted index queries",
            "recommended_family": "Search/Document",
            "recommended_db": "Elasticsearch",
            "rationale": "Inverted index, fuzzy matching, and real-time faceted aggregations"
        },
        {
            "app": "E-Commerce Platform",
            "domain": "recommendation_graph",
            "description": "Customers-who-bought-X-also-bought-Y and co-purchase networks",
            "read_write_pattern": "Multi-hop graph traversals",
            "recommended_family": "Graph",
            "recommended_db": "Neo4j",
            "rationale": "Fast traversal of user-product purchase relationships"
        },
    ]

    # --- IoT Smart Home Platform ---
    print("=== IoT Smart Home Platform ===")
    iot_domains = [
        {
            "app": "IoT Smart Home",
            "domain": "device_registry",
            "description": "Smart thermostats, cameras, locks, firmware versions, and room metadata",
            "read_write_pattern": "Read-heavy, infrequent configuration updates",
            "recommended_family": "Document",
            "recommended_db": "MongoDB",
            "rationale": "Nested device capabilities and per-manufacturer metadata"
        },
        {
            "app": "IoT Smart Home",
            "domain": "sensor_telemetry",
            "description": "Continuous temperature, humidity, and power usage readings every second",
            "read_write_pattern": "High-volume append-only writes, time-range scans",
            "recommended_family": "Wide-Column",
            "recommended_db": "Apache Cassandra",
            "rationale": "Linear write scaling and time-bucketed partitioning"
        },
        {
            "app": "IoT Smart Home",
            "domain": "live_device_state",
            "description": "Current online/offline status and latest trigger flags per device",
            "read_write_pattern": "Frequent overwrites and instant dashboard lookups",
            "recommended_family": "Key-Value",
            "recommended_db": "Redis",
            "rationale": "O(1) key lookups and pub/sub notifications for instant alerts"
        },
        {
            "app": "IoT Smart Home",
            "domain": "video_clips_archive",
            "description": "Motion-triggered security camera footage and snapshots",
            "read_write_pattern": "Write-once binary blobs, lifecycle archival",
            "recommended_family": "Object/Key-Value",
            "recommended_db": "Amazon S3",
            "rationale": "Durable, cost-effective object storage with automated tiering"
        },
    ]

    all_domains = ecommerce_domains + iot_domains
    col.insert_many(all_domains)
    print(f"[OK] Inserted {len(all_domains)} domain mappings.\n")

    # Print tables per application
    for app_name in ["E-Commerce Platform", "IoT Smart Home"]:
        table = Table(title=f"{app_name} - Data Domain Mapping", show_lines=True)
        table.add_column("Domain", style="cyan", width=22)
        table.add_column("Description", width=52)
        table.add_column("NoSQL Family", style="magenta", width=16)
        table.add_column("Recommended DB", style="green", width=20)
        table.add_column("Key Rationale", width=48)

        for d in col.find({"app": app_name}):
            table.add_row(
                d["domain"], d["description"], d["recommended_family"],
                d["recommended_db"], d["rationale"]
            )
        console.print(table)
        print()

    # Summary: family distribution
    print("--- Family Distribution (Try It Yourself) ---")
    pipeline = [
        {"$group": {"_id": "$recommended_family", "count": {"$sum": 1}, "domains": {"$push": "$domain"}}},
        {"$sort": {"count": -1}}
    ]
    for g in col.aggregate(pipeline):
        print(f"  {g['_id']:20} : {g['count']} domain(s) -> {', '.join(g['domains'])}")

    banner("Lab 1.2 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
