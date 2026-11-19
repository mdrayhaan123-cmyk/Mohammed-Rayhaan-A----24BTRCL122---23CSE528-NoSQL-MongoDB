import os
import sys
import time
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
import schedule
from tabulate import tabulate
from connection import get_client, get_mongo_uri

def run_mongodump(uri: str, base_backup_dir: str, db_name: str = None) -> str:
    os.makedirs(base_backup_dir, exist_ok=True)
    ts_folder = datetime.now(timezone.utc).strftime("backup_%Y%m%d_%H%M%S_%f")
    out_dir = os.path.join(base_backup_dir, ts_folder)
    cmd = ["mongodump", "--uri", uri, "--out", out_dir, "--quiet"]
    if db_name:
        cmd.extend(["--db", db_name])
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"mongodump failed (rc={res.returncode}): {res.stderr}")
    return out_dir

def enforce_retention_policy(base_backup_dir: str, retention_days: int = 7) -> list:
    cutoff = time.time() - (retention_days * 86400)
    entries = []
    for name in os.listdir(base_backup_dir):
        full_path = os.path.join(base_backup_dir, name)
        if os.path.isdir(full_path):
            entries.append((os.path.getmtime(full_path), full_path))
    entries.sort(key=lambda x: x[0])

    deleted = []
    for mtime, folder in entries:
        if mtime < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
            deleted.append(os.path.basename(folder))
    return deleted

def verify_point_in_time_restore(client, uri: str, db_name: str, backup_root: str):
    print("\n--- Step 1: Point-in-Time Backup & Restore Integrity Verification (1,000 Docs) ---")
    db = client[db_name]
    coll = db["backup_test"]
    coll.drop()

    expected_docs = [
        {
            "doc_id": i,
            "account": f"ACC-{1000+i}",
            "verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(1, 1001)
    ]
    coll.insert_many(expected_docs)
    print(f"  [INSERTED] 1,000 baseline documents into '{db_name}.backup_test' (verified=True)")

    # Take pre-mutation backup
    dump_dir = run_mongodump(uri, backup_root, db_name=db_name)
    print(f"  [BACKUP OK] Created timestamped dump at '{dump_dir}'")

    # Simulate accidental data corruption / bad bulk update
    coll.update_many({}, {"$set": {"verified": False}})
    corrupted_count = coll.count_documents({"verified": False})
    print(f"  [MUTATED] Simulated accidental update -> {corrupted_count} docs now have verified=False")

    # Restore from backup using mongorestore --drop --nsInclude
    ns_pattern = f"{db_name}.backup_test"
    restore_cmd = [
        "mongorestore",
        "--uri", uri,
        "--drop",
        f"--nsInclude={ns_pattern}",
        dump_dir,
        "--quiet",
    ]
    res = subprocess.run(restore_cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"mongorestore failed (rc={res.returncode}): {res.stderr}")

    # Assert exact recovery of count and field values
    restored_docs = list(coll.find({}, {"_id": 0}).sort("doc_id", 1))
    assert len(restored_docs) == 1000, f"Count mismatch: expected 1000, got {len(restored_docs)}"
    for orig, rest in zip(expected_docs, restored_docs):
        assert rest["verified"] is True, f"Field mismatch on doc_id={rest['doc_id']}"
        assert rest["account"] == orig["account"], f"Account mismatch on doc_id={rest['doc_id']}"
    print("  [RESTORE VERIFIED] Assertion loop passed: 1,000/1,000 documents recovered with verified=True")

def run_scale_benchmarks(client, uri: str, db_name: str, backup_root: str):
    print("\n--- Step 2: RPO / RTO Scaling Benchmarks (1,000 | 10,000 | 100,000 Documents) ---")
    db = client[db_name]
    volumes = [1000, 10000, 100000]
    results = []
    payload_pad = "X" * 900  # ~1 KB per document -> 100k docs ~= 100 MB

    for count in volumes:
        bench_coll = db[f"bench_{count}"]
        bench_coll.drop()

        # Batch insert in chunks of 10,000
        batch_size = 10000
        for start in range(0, count, batch_size):
            end = min(start + batch_size, count)
            docs = [{"seq": i, "tier": count, "payload": payload_pad} for i in range(start, end)]
            bench_coll.insert_many(docs, ordered=False)

        stats = db.command("collStats", f"bench_{count}")
        size_mb = round(stats.get("size", 0) / (1024 * 1024), 2)

        # Measure mongodump time
        t0 = time.perf_counter()
        dump_dir = run_mongodump(uri, backup_root, db_name=db_name)
        dump_sec = round(time.perf_counter() - t0, 3)

        # Measure mongorestore time
        ns_include = f"{db_name}.bench_{count}"
        t1 = time.perf_counter()
        res = subprocess.run(
            ["mongorestore", "--uri", uri, "--drop", f"--nsInclude={ns_include}", dump_dir, "--quiet"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Benchmark restore failed: {res.stderr}")
        restore_sec = round(time.perf_counter() - t1, 3)

        # RPO = 1 hour (3600s) scheduled interval; RTO = restore_sec + 5.0s app reconnect/restart overhead
        rto_sec = round(restore_sec + 5.0, 2)
        results.append([f"{count:,}", f"{size_mb} MB", f"{dump_sec} s", f"{restore_sec} s", "1 Hour (Hourly)", f"{rto_sec} s"])

        # Drop large benchmark collections after recording metrics to keep Compass snappy
        if count > 1000:
            bench_coll.drop()

    print(tabulate(
        results,
        headers=["Documents", "Uncompressed Size", "mongodump Time", "mongorestore Time", "Target RPO", "Estimated RTO"],
        tablefmt="grid",
    ))

    # Persist benchmark summary into lab_14.rpo_rto_benchmarks for Compass inspection
    db.rpo_rto_benchmarks.drop()
    db.rpo_rto_benchmarks.insert_many([
        {
            "documents": r[0],
            "uncompressed_size": r[1],
            "mongodump_time": r[2],
            "mongorestore_time": r[3],
            "rpo": r[4],
            "rto": r[5],
        }
        for r in results
    ])

def main():
    print("=" * 78)
    print("LAB 14.2: Automated Backup, Point-in-Time Restore & RPO/RTO Benchmarks")
    print("=" * 78)

    uri = sys.argv[1] if len(sys.argv) > 1 else get_mongo_uri()
    backup_root = sys.argv[2] if len(sys.argv) > 2 else os.getenv("BACKUP_DIR", "/app/backups")
    db_name = os.getenv("DB_NAME", "lab_14")

    client = get_client()

    # Register hourly schedule job and verify scheduler registration
    schedule.clear()
    schedule.every().hour.do(run_mongodump, uri=uri, base_backup_dir=backup_root, db_name=db_name)
    print(f"[SCHEDULER] Registered hourly backup job: {schedule.get_jobs()[0]}")

    # Create a simulated 9-day-old backup folder to verify 7-day retention cleanup
    stale_dir = os.path.join(backup_root, "backup_expired_9d_ago")
    os.makedirs(stale_dir, exist_ok=True)
    nine_days_ago = time.time() - (9 * 86400)
    os.utime(stale_dir, (nine_days_ago, nine_days_ago))

    verify_point_in_time_restore(client, uri, db_name, backup_root)
    run_scale_benchmarks(client, uri, db_name, backup_root)

    purged = enforce_retention_policy(backup_root, retention_days=7)
    print(f"\n[RETENTION POLICY] Enforced 7-day retention window -> purged expired folders: {purged}")

if __name__ == "__main__":
    main()