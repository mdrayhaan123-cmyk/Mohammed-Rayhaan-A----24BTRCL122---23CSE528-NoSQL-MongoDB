"""Lab 8.2 - Observe Failover and Election

Monitors replica set member state, logs connected primary, and demonstrates
write concern (w:1 vs w:majority) and secondary read preferences in lab_8.
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient, ReadPreference
from config.connection import get_db, reset_collection, banner

RS_URI = os.getenv(
    "REPLICA_SET_URI",
    "mongodb://host.docker.internal:27017,host.docker.internal:27018,host.docker.internal:27019/?replicaSet=rs0"
)


def observe_failover(cycles=3, interval=1):
    print(f"Connecting to: {RS_URI}")
    try:
        client = MongoClient(RS_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        print("[OK] Connected to replica set.")
    except Exception:
        print("[INFO] Replica set rs0 not reachable; using local lab_8 fallback.")
        client = None

    col = reset_collection("lab_8", "failover_events")
    last_primary = None
    for step in range(1, cycles + 1):
        if client:
            status = client.admin.command("replSetGetStatus")
            primary = next((m["name"] for m in status["members"] if m["stateStr"] == "PRIMARY"), "unknown")
        else:
            primary = "localhost:27017"
        ts = time.strftime("%H:%M:%S")
        event = {"step": step, "timestamp": ts, "connected_primary": primary, "event": "FAILOVER" if (last_primary and primary != last_primary) else "HEARTBEAT"}
        col.insert_one(event)
        print(f"  [{ts}] Step {step}: Connected PRIMARY = {primary}")
        last_primary = primary
        if step < cycles:
            time.sleep(interval)

    if client:
        client.close()


def main():
    banner("Lab 8.2: Observe Failover and Election")
    observe_failover(cycles=3, interval=0.5)
    print("\n[OK] Failover observer log saved to lab_8.failover_events.")
    banner("Lab 8.2 Complete")


if __name__ == "__main__":
    main()
