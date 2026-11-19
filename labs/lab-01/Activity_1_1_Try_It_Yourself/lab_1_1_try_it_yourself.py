"""Lab 1.1 (Try It Yourself) - Extended NoSQL Product Classification

Classifies the 3 mystery products from Lab 1.1 plus additional modern NoSQL engines,
stores them in MongoDB, and analyzes distribution by family and license model.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner, print_json
from rich.table import Table
from rich.console import Console

console = Console()


def main():
    banner("Lab 1.1 (Try It Yourself): Extended NoSQL Product Classification")

    db = get_db("lab_1")
    col = reset_collection("lab_1", "database_products_diy")

    # Classify mystery products from Lab 1.1 + additional real-world NoSQL databases
    diy_products = [
        {"name": "Amazon DynamoDB", "family": "Key-Value / Document", "data_model": "Key-Value & JSON Document",
         "vendor": "AWS", "use_case": "Shopping carts, session state, serverless backends", "open_source": False},
        {"name": "InfluxDB", "family": "Time-Series", "data_model": "Time-Stamped Measurements & Tags",
         "vendor": "InfluxData", "use_case": "IoT sensor metrics, DevOps monitoring, real-time telemetry", "open_source": True},
        {"name": "OrientDB", "family": "Multi-Model", "data_model": "Document + Graph Hybrid",
         "vendor": "SAP / OrientDB", "use_case": "Fraud detection, master data management, social graphs", "open_source": True},
        {"name": "ScyllaDB", "family": "Wide-Column", "data_model": "Column-Family (C++ Cassandra-compatible)",
         "vendor": "ScyllaDB Inc.", "use_case": "Low-latency ad-tech, IoT ingestion, messaging", "open_source": True},
        {"name": "ArangoDB", "family": "Multi-Model", "data_model": "Document + Graph + Key-Value",
         "vendor": "ArangoDB Inc.", "use_case": "Knowledge graphs, identity resolution, microservices", "open_source": True},
        {"name": "Riak KV", "family": "Key-Value", "data_model": "Distributed Key-Value (Dynamo-style)",
         "vendor": "TIOT / Basho", "use_case": "High-availability session stores, shopping carts", "open_source": True},
        {"name": "Apache CouchDB", "family": "Document", "data_model": "JSON Document (MVCC + HTTP API)",
         "vendor": "Apache", "use_case": "Offline-first mobile sync, distributed web apps", "open_source": True},
        {"name": "TigerGraph", "family": "Graph", "data_model": "Native Parallel Property Graph",
         "vendor": "TigerGraph", "use_case": "Deep-link analytics, supply chain, anti-money laundering", "open_source": False},
    ]

    col.insert_many(diy_products)
    print(f"[OK] Inserted {len(diy_products)} extended NoSQL products.\n")

    # Display sorted classification table
    table = Table(title="Extended NoSQL Product Classification (Try It Yourself)", show_lines=True)
    table.add_column("Product", style="cyan", width=18)
    table.add_column("Family", style="magenta", width=22)
    table.add_column("Vendor", style="green", width=15)
    table.add_column("Open Source", width=12)
    table.add_column("Primary Use Case", width=45)

    for p in col.find().sort("family"):
        os_label = "Yes" if p["open_source"] else "No (Managed)"
        table.add_row(p["name"], p["family"], p["vendor"], os_label, p["use_case"])

    console.print(table)

    # Aggregation 1: Group by NoSQL family
    print("\n--- Grouped by NoSQL Family ---")
    family_pipeline = [
        {"$group": {"_id": "$family", "count": {"$sum": 1}, "products": {"$push": "$name"}}},
        {"$sort": {"count": -1}}
    ]
    for grp in col.aggregate(family_pipeline):
        print(f"  {grp['_id']:22} : {grp['count']} product(s) -> {', '.join(grp['products'])}")

    # Aggregation 2: Group by open-source availability
    print("\n--- Open-Source vs. Proprietary Breakdown ---")
    license_pipeline = [
        {"$group": {"_id": "$open_source", "count": {"$sum": 1}, "products": {"$push": "$name"}}},
        {"$sort": {"count": -1}}
    ]
    for grp in col.aggregate(license_pipeline):
        label = "Open Source" if grp["_id"] else "Proprietary/Managed"
        print(f"  {label:22} : {grp['count']} product(s) -> {', '.join(grp['products'])}")

    banner("Lab 1.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
