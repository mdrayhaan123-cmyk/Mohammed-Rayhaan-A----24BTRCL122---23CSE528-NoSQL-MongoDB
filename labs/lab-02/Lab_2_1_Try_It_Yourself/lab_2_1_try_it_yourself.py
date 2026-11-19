"""Lab 2.1 (Try It Yourself) - Compare MongoDB Atlas and Docker Server Versions

Connects to both local/Docker MongoDB and MongoDB Atlas (when MONGO_URI_ATLAS
is configured in .env), compares their server_info() metadata, and stores
the comparison in MongoDB.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

from pymongo import MongoClient
from config.connection import get_db, reset_collection, banner
from rich.console import Console
from rich.table import Table

console = Console()


def fetch_server_details(label: str, uri: str) -> dict:
    """Connect to a MongoDB deployment and extract server_info() details."""
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    info = client.server_info()
    client.close()
    return {
        "deployment": label,
        "uri_target": uri.split("@")[-1] if "@" in uri else uri,
        "version": info.get("version", "unknown"),
        "git_version": info.get("gitVersion", "N/A")[:12],
        "storage_engines": ", ".join(info.get("storageEngines", [])),
        "max_bson_mb": round(info.get("maxBsonObjectSize", 0) / (1024 * 1024), 2),
        "modules": ", ".join(info.get("modules", [])) or "community",
    }


def main():
    banner("Lab 2.1 (Try It Yourself): Atlas vs. Docker MongoDB")

    docker_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    atlas_uri = os.getenv("MONGO_URI_ATLAS", "").strip()

    docker_info = fetch_server_details("Docker / Local MongoDB", docker_uri)
    records = [docker_info]

    if atlas_uri and "example.mongodb.net" not in atlas_uri:
        try:
            atlas_info = fetch_server_details("MongoDB Atlas (Cloud)", atlas_uri)
        except Exception as e:
            print(f"[WARN] Could not reach MongoDB Atlas ({e}).")
            atlas_info = {
                "deployment": "MongoDB Atlas (Cloud)",
                "uri_target": "unreachable",
                "version": "N/A (check URI / Network Access)",
                "git_version": "N/A",
                "storage_engines": "N/A",
                "max_bson_mb": "N/A",
                "modules": "N/A",
            }
    else:
        print("[INFO] MONGO_URI_ATLAS not set in .env; showing local deployment only.")
        atlas_info = {
            "deployment": "MongoDB Atlas (Cloud)",
            "uri_target": "not configured",
            "version": "Not configured in .env",
            "git_version": "N/A",
            "storage_engines": "N/A",
            "max_bson_mb": "N/A",
            "modules": "N/A",
        }

    records.append(atlas_info)

    # Store comparison results in MongoDB
    col = reset_collection("lab_2", "server_comparison")
    col.insert_many(records)
    print("[OK] Saved server_info() comparison to nosql_labs.server_comparison.\n")

    # Display side-by-side comparison table
    table = Table(title="MongoDB server_info() Comparison: Docker/Local vs. Atlas", show_lines=True)
    table.add_column("Property", style="cyan", width=20)
    table.add_column("Docker / Local MongoDB", style="green", width=34)
    table.add_column("MongoDB Atlas (Cloud)", style="magenta", width=34)

    fields = [
        ("MongoDB Version", "version"),
        ("Git Commit", "git_version"),
        ("Storage Engines", "storage_engines"),
        ("Max BSON Size (MB)", "max_bson_mb"),
        ("Edition / Modules", "modules"),
    ]
    for label, key in fields:
        table.add_row(label, str(docker_info[key]), str(atlas_info[key]))

    console.print(table)
    banner("Lab 2.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
