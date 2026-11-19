import time
import uuid
import random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import ReturnDocument
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError, OperationFailure
from connection import get_client, get_db

def seed_inventory(db, stock: int = 5):
    db.inventory.drop()
    db.orders.drop()
    db.inventory.insert_one({
        "product_id": "PROD-CTI-01",
        "name": "Hardware Security Key HSM-X",
        "stock": stock,
        "price": 149.99,
        "version": 1,
    })

def reserve_inventory_once(client, db, customer_id: str, product_id: str, qty: int):
    with client.start_session() as session:
        with session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority", wtimeout=5000),
        ):
            item = db.inventory.find_one({"product_id": product_id}, session=session)
            if not item:
                raise ValueError(f"Product {product_id} not found")
            if item["stock"] < qty:
                raise ValueError(f"Out of stock (available={item['stock']}, requested={qty})")

            upd = db.inventory.update_one(
                {"product_id": product_id, "version": item["version"], "stock": {"$gte": qty}},
                {"$inc": {"stock": -qty, "version": 1}},
                session=session,
            )
            if upd.modified_count != 1:
                raise RuntimeError("Optimistic concurrency version mismatch")

            order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            db.orders.insert_one(
                {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "items": [{"product_id": product_id, "qty": qty, "price": item["price"]}],
                    "status": "PENDING",
                    "total": round(qty * item["price"], 2),
                    "created_at": datetime.now(timezone.utc),
                },
                session=session,
            )
            return order_id

def reserve_inventory(client, db, customer_id: str, product_id: str, qty: int = 1, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            order_id = reserve_inventory_once(client, db, customer_id, product_id, qty)
            return {"ok": True, "order_id": order_id, "attempts": attempt + 1}
        except (OperationFailure, PyMongoError) as exc:
            is_transient = (getattr(exc, "code", None) == 112) or exc.has_error_label("TransientTransactionError")
            if is_transient and attempt < max_retries - 1:
                time.sleep(0.02 * (2 ** attempt) + random.uniform(0, 0.01))
                continue
            return {"ok": False, "reason": f"WriteConflict/Transient after {attempt + 1} tries", "attempts": attempt + 1}
        except (ValueError, RuntimeError) as exc:
            if "version mismatch" in str(exc) and attempt < max_retries - 1:
                time.sleep(0.015 * (attempt + 1))
                continue
            return {"ok": False, "reason": str(exc), "attempts": attempt + 1}
    return {"ok": False, "reason": "Exhausted retries", "attempts": max_retries}

def non_transactional_reserve(db, customer_id: str, product_id: str, qty: int = 1):
    updated = db.inventory.find_one_and_update(
        {"product_id": product_id, "stock": {"$gte": qty}},
        {"$inc": {"stock": -qty, "version": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        return {"ok": False, "reason": "Out of stock"}
    order_id = f"ORD-NT-{uuid.uuid4().hex[:6].upper()}"
    db.orders.insert_one({
        "order_id": order_id,
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "qty": qty, "price": updated["price"]}],
        "status": "PENDING",
        "total": round(qty * updated["price"], 2),
    })
    return {"ok": True, "order_id": order_id}

def run_contention_test(client, db):
    print("\n--- Contention Test: 8 Concurrent Threads vs Stock = 5 ---")
    seed_inventory(db, stock=5)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(reserve_inventory, client, db, f"CUST-{i:02d}", "PROD-CTI-01", 1, 5)
            for i in range(1, 9)
        ]
        results = [f.result() for f in as_completed(futures)]

    succeeded = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    final_item = db.inventory.find_one({"product_id": "PROD-CTI-01"}, {"_id": 0})
    print(f"  Succeeded: {len(succeeded)}/8 | Failed: {len(failed)}/8")
    print(f"  Final Inventory: {final_item} | Orders Created: {db.orders.count_documents({})}")
    for f in failed:
        print(f"  Rejected Request -> {f['reason']} (attempts={f['attempts']})")

def benchmark_throughput(client, db):
    print("\n--- Concurrency Throughput Benchmark (1, 4, 8, 16 Threads) ---")
    levels = [1, 4, 8, 16]
    total_requests = 24
    for workers in levels:
        seed_inventory(db, stock=100)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(reserve_inventory, client, db, f"BENCH-{i}", "PROD-CTI-01", 1, 6)
                for i in range(total_requests)
            ]
            res = [f.result() for f in as_completed(futures)]
        elapsed = time.perf_counter() - t0
        ok_count = sum(1 for r in res if r["ok"])
        tps = ok_count / elapsed if elapsed > 0 else 0
        print(f"  [TXN  | workers={workers:2d}] Success={ok_count}/{total_requests} | Elapsed={elapsed:.3f}s | Throughput={tps:6.2f} tx/s")

    seed_inventory(db, stock=100)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [
            pool.submit(non_transactional_reserve, db, f"NT-{i}", "PROD-CTI-01", 1)
            for i in range(total_requests)
        ]
        res_nt = [f.result() for f in as_completed(futures)]
    elapsed_nt = time.perf_counter() - t0
    ok_nt = sum(1 for r in res_nt if r["ok"])
    print(f"  [NO-TX| workers= 8] Success={ok_nt}/{total_requests} | Elapsed={elapsed_nt:.3f}s | Throughput={ok_nt/elapsed_nt:6.2f} ops/s (Higher speed, no rollback safety)")

def main():
    print("=" * 68)
    print("LAB 10.2: Inventory Reservation with Deadlock/WriteConflict Handling")
    print("=" * 68)
    client = get_client()
    db = get_db(client)
    run_contention_test(client, db)
    benchmark_throughput(client, db)

if __name__ == "__main__":
    main()