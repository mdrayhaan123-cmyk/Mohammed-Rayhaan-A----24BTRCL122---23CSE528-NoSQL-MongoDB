from datetime import datetime, timezone
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from pymongo.errors import PyMongoError
from connection import get_client, get_db

def setup_accounts(db):
    db.accounts.drop()
    db.transfer_history.drop()
    db.accounts.insert_many([
        {"account_id": "ACC-1001", "owner": "Alice", "balance": 1000.0, "version": 1},
        {"account_id": "ACC-1002", "owner": "Bob", "balance": 500.0, "version": 1},
    ])
    print("[SETUP] Inserted ACC-1001 ($1000.00) and ACC-1002 ($500.00)")

def transfer_funds(client, db, from_acc: str, to_acc: str, amount: float):
    if amount <= 0:
        raise ValueError("Transfer amount must be positive.")

    with client.start_session() as session:
        with session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority", wtimeout=5000),
        ):
            src = db.accounts.find_one({"account_id": from_acc}, session=session)
            dst = db.accounts.find_one({"account_id": to_acc}, session=session)
            if not src or not dst:
                raise ValueError("Source or destination account not found.")
            if src["balance"] < amount:
                raise ValueError(
                    f"Insufficient funds in {from_acc}: balance=${src['balance']:.2f}, requested=${amount:.2f}"
                )

            debit_res = db.accounts.update_one(
                {"account_id": from_acc, "balance": {"$gte": amount}},
                {"$inc": {"balance": -amount, "version": 1}},
                session=session,
            )
            if debit_res.modified_count != 1:
                raise RuntimeError("Debit failed due to concurrent balance modification or insufficient funds.")

            credit_res = db.accounts.update_one(
                {"account_id": to_acc},
                {"$inc": {"balance": amount, "version": 1}},
                session=session,
            )
            if credit_res.modified_count != 1:
                raise RuntimeError("Credit failed on destination account.")

            db.transfer_history.insert_one(
                {
                    "from_account": from_acc,
                    "to_account": to_acc,
                    "amount": amount,
                    "status": "COMMITTED",
                    "timestamp": datetime.now(timezone.utc),
                },
                session=session,
            )

def print_balances(db, label: str):
    docs = list(db.accounts.find({}, {"_id": 0}).sort("account_id", 1))
    print(f"[{label}] Accounts: {docs} | History count: {db.transfer_history.count_documents({})}")

def main():
    print("=" * 68)
    print("LAB 10.1: Multi-Document Bank Transfer Transaction")
    print("=" * 68)
    client = get_client()
    db = get_db(client)
    setup_accounts(db)
    print_balances(db, "INITIAL")

    print("\n--- Test 1: Valid Transfer ($250.00 from ACC-1001 -> ACC-1002) ---")
    transfer_funds(client, db, "ACC-1001", "ACC-1002", 250.0)
    print("[OK] Transaction committed.")
    print_balances(db, "AFTER VALID TRANSFER")

    print("\n--- Test 2: Insufficient Funds ($2000.00 from ACC-1001 -> ACC-1002) ---")
    try:
        transfer_funds(client, db, "ACC-1001", "ACC-1002", 2000.0)
    except (ValueError, PyMongoError) as exc:
        print(f"[ROLLBACK TRIGGERED] {exc}")
    print_balances(db, "AFTER ROLLBACK (UNCHANGED)")

if __name__ == "__main__":
    main()