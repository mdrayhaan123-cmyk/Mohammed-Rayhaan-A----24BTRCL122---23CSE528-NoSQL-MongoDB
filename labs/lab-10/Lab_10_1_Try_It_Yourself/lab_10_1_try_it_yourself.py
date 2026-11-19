import time
import random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError
from connection import get_client, get_db

def execute_transfer_once(client, db, from_acc: str, to_acc: str, amount: float):
    with client.start_session() as session:
        with session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority", wtimeout=5000),
        ):
            src = db.accounts.find_one({"account_id": from_acc}, session=session)
            if not src or src["balance"] < amount:
                raise ValueError(f"Insufficient funds in {from_acc}")

            debit = db.accounts.update_one(
                {"account_id": from_acc, "balance": {"$gte": amount}},
                {"$inc": {"balance": -amount, "version": 1}},
                session=session,
            )
            if debit.modified_count != 1:
                raise RuntimeError("Optimistic/balance guard prevented debit")

            db.accounts.update_one(
                {"account_id": to_acc},
                {"$inc": {"balance": amount, "version": 1}},
                session=session,
            )
            db.transfer_history.insert_one(
                {
                    "from_account": from_acc,
                    "to_account": to_acc,
                    "amount": amount,
                    "status": "COMMITTED_WITH_RETRY",
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

def transfer_with_exponential_backoff(client, db, from_acc: str, to_acc: str, amount: float, max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            execute_transfer_once(client, db, from_acc, to_acc, amount)
            return {"status": "COMMITTED", "attempts": attempt + 1}
        except PyMongoError as exc:
            if exc.has_error_label("TransientTransactionError") and attempt < max_retries - 1:
                backoff = (0.1 * (2 ** attempt)) + random.uniform(0.0, 0.03)
                print(f"  [RETRY] TransientTransactionError on attempt {attempt + 1}; sleeping {backoff:.3f}s")
                time.sleep(backoff)
                continue
            return {"status": f"FAILED_MONGO: {exc}", "attempts": attempt + 1}
        except ValueError as exc:
            return {"status": f"ABORTED: {exc}", "attempts": attempt + 1}
    return {"status": "EXHAUSTED_RETRIES", "attempts": max_retries}

def main():
    print("=" * 68)
    print("LAB 10.1 (Try It Yourself): Exponential Backoff for TransientTransactionError")
    print("=" * 68)
    client = get_client()
    db = get_db(client)
    db.accounts.drop()
    db.transfer_history.drop()
    db.accounts.insert_many([
        {"account_id": "ACC-1001", "owner": "Alice", "balance": 500.0, "version": 1},
        {"account_id": "ACC-1002", "owner": "Bob", "balance": 500.0, "version": 1},
    ])

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(transfer_with_exponential_backoff, client, db, "ACC-1001", "ACC-1002", 100.0)
            for _ in range(6)
        ]
        results = [f.result() for f in as_completed(futures)]

    committed = sum(1 for r in results if r["status"] == "COMMITTED")
    aborted = len(results) - committed
    for idx, res in enumerate(results, 1):
        print(f"  Worker #{idx}: {res}")

    final_accounts = list(db.accounts.find({}, {"_id": 0}).sort("account_id", 1))
    print(f"\n[SUMMARY] Committed={committed}, Aborted={aborted}")
    print(f"[FINAL STATE] {final_accounts}")

if __name__ == "__main__":
    main()