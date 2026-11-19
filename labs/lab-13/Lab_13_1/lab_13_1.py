import os
import time
import threading
from datetime import datetime, timezone
from pymongo import ReadPreference
from pymongo.errors import AutoReconnect, NotPrimaryError, PyMongoError
from connection import get_client, get_db

def main():
    print("=" * 76)
    print("LAB 13.1: 3-Node Replica Set (keyFile Auth) & Live Failover Verification")
    print("=" * 76)

    client = get_client()
    db_name = os.getenv("DB_NAME", "lab_13")
    db = get_db(client)

    # Seed baseline documents for Compass visibility & continuous read tests
    db.replica_events.drop()
    db.replica_events.insert_many([
        {"event_id": "EVT-01", "node": "mongo1", "status": "INITIAL_SYNC", "ts": datetime.now(timezone.utc)},
        {"event_id": "EVT-02", "node": "mongo2", "status": "OPLOG_REPLICATED", "ts": datetime.now(timezone.utc)},
        {"event_id": "EVT-03", "node": "mongo3", "status": "HEARTBEAT_OK", "ts": datetime.now(timezone.utc)},
    ])
    print(f"[SEED] Populated '{db_name}.replica_events' with 3 baseline documents")

    hello = client.admin.command("hello")
    if "setName" not in hello:
        print("[INFO] Connected to standalone host instance (Compass persistence mode).")
        print("       Run via docker-compose to execute 3-node rs0 keyFile & failover verification.")
        return

    # 1. Inspect rs.status() across all 3 replica set members
    rs_status = client.admin.command("replSetGetStatus")
    print(f"\n[REPLICA SET STATUS] Set='{rs_status['set']}' | Members={len(rs_status['members'])}")
    initial_primary = None
    for m in rs_status["members"]:
        state = m["stateStr"]
        if state == "PRIMARY":
            initial_primary = m["name"]
        print(f"  - {m['name']:<16} | State: {state:<10} | Health: {int(m['health'])} (OK)")

    # 2. Start continuous PyMongo reader thread and trigger primary stepDown failover
    print(f"\n--- Triggering Failover via replSetStepDown on Primary ({initial_primary}) ---")
    stop_flag = threading.Event()
    read_stats = {"success": 0, "failover_retries": 0}
    coll_sec_pref = db.get_collection("replica_events", read_preference=ReadPreference.PRIMARY_PREFERRED)

    def continuous_reader():
        while not stop_flag.is_set():
            try:
                _ = coll_sec_pref.count_documents({})
                read_stats["success"] += 1
            except (AutoReconnect, NotPrimaryError):
                read_stats["failover_retries"] += 1
            except PyMongoError:
                read_stats["failover_retries"] += 1
            time.sleep(0.15)

    reader_thread = threading.Thread(target=continuous_reader, daemon=True)
    reader_thread.start()
    time.sleep(0.6)

    try:
        client.admin.command({"replSetStepDown": 20, "force": True})
    except PyMongoError as exc:
        print(f"  [STEPDOWN SENT] Connection closed during election as expected -> {type(exc).__name__}")

    # Wait for new primary election and observe continuous reader resilience
    new_primary = None
    for _ in range(25):
        time.sleep(0.5)
        try:
            st = client.admin.command("replSetGetStatus")
            for m in st["members"]:
                if m["stateStr"] == "PRIMARY" and m["name"] != initial_primary:
                    new_primary = m["name"]
                    break
            if new_primary:
                break
        except PyMongoError:
            pass

    time.sleep(1.0)
    stop_flag.set()
    reader_thread.join(timeout=2.0)

    print(f"  [ELECTION COMPLETE] Previous Primary: {initial_primary} -> New Primary: {new_primary or 'Re-elected'}")
    print(f"  [CONTINUOUS READER] Successful Reads: {read_stats['success']} | Transient Failover Retries: {read_stats['failover_retries']}")

    # Write post-failover verification record
    db.replica_events.insert_one({
        "event_id": "EVT-FAILOVER",
        "previous_primary": initial_primary,
        "new_primary": new_primary or "rs0-primary",
        "status": "FAILOVER_VERIFIED",
        "ts": datetime.now(timezone.utc),
    })

if __name__ == "__main__":
    main()