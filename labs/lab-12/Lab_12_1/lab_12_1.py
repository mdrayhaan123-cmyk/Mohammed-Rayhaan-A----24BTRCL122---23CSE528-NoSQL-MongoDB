import os
from pymongo.errors import OperationFailure
from connection import wait_for_mongo, build_client

def main():
    print("=" * 76)
    print("LAB 12.1: Authentication & Least-Privilege Role-Based Access Control (RBAC)")
    print("=" * 76)

    db_name = os.getenv("DB_NAME", "lab_12")
    admin_user = os.getenv("MONGO_ADMIN_USER", "")
    admin_pass = os.getenv("MONGO_ADMIN_PASS", "")

    admin_client = wait_for_mongo()
    db = admin_client[db_name]
    admin_db = admin_client["admin"]

    # Seed sample collections for Compass inspection and RBAC verification
    db.orders.drop()
    db.products.drop()
    db.orders.insert_many([
        {"order_id": "ORD-101", "item": "HSM-X Security Module", "qty": 2, "status": "SHIPPED"},
        {"order_id": "ORD-102", "item": "TLS Hardware Accelerator", "qty": 1, "status": "PENDING"},
    ])
    db.products.insert_many([
        {"sku": "SKU-01", "name": "HSM-X Security Module", "price": 149.99},
        {"sku": "SKU-02", "name": "TLS Hardware Accelerator", "price": 299.00},
    ])
    print(f"[SEED] Populated '{db_name}.orders' (2 docs) and '{db_name}.products' (2 docs)")

    if not admin_user:
        print("[INFO] Running against unauthenticated host instance (Compass persistence mode).")
        print("       Enable MONGO_ADMIN_USER / --auth via docker-compose to enforce RBAC checks.")
        return

    # 1. Create custom least-privilege roles in admin database
    for role_name in ("lab12ReaderRole", "lab12OrderWriterRole"):
        try:
            admin_db.command("dropRole", role_name)
        except OperationFailure:
            pass

    admin_db.command(
        "createRole",
        "lab12ReaderRole",
        privileges=[
            {"resource": {"db": db_name, "collection": "orders"}, "actions": ["find"]},
            {"resource": {"db": db_name, "collection": "products"}, "actions": ["find"]},
        ],
        roles=[],
    )
    admin_db.command(
        "createRole",
        "lab12OrderWriterRole",
        privileges=[
            {
                "resource": {"db": db_name, "collection": "orders"},
                "actions": ["find", "insert", "update", "remove"],
            }
        ],
        roles=[],
    )
    print("[RBAC] Created custom roles: 'lab12ReaderRole' and 'lab12OrderWriterRole'")

    # 2. Create application users mapped to custom roles
    for user_name in ("app_user_read", "app_user_write"):
        try:
            admin_db.command("dropUser", user_name)
        except OperationFailure:
            pass

    admin_db.command(
        "createUser",
        "app_user_read",
        pwd="ReadPass123!",
        roles=[{"role": "lab12ReaderRole", "db": "admin"}],
    )
    admin_db.command(
        "createUser",
        "app_user_write",
        pwd="WritePass123!",
        roles=[{"role": "lab12OrderWriterRole", "db": "admin"}],
    )
    print("[USERS] Created 'app_user_read' and 'app_user_write'")

    # 3. Verify app_user_read privileges
    print("\n--- Testing app_user_read (Read-Only on orders & products) ---")
    read_client = build_client(username="app_user_read", password="ReadPass123!")
    orders_found = read_client[db_name].orders.count_documents({})
    print(f"  [ALLOWED] find() on {db_name}.orders -> count={orders_found}")

    try:
        read_client[db_name].orders.insert_one({"order_id": "ORD-999", "item": "Unauthorized"})
        print("  [ERROR] Write unexpectedly succeeded!")
    except OperationFailure as exc:
        print(f"  [DENIED AS EXPECTED] insert_one() rejected -> code={exc.code} ({exc.details.get('codeName')})")

    # 4. Verify app_user_write privileges
    print("\n--- Testing app_user_write (Read/Write on orders only) ---")
    write_client = build_client(username="app_user_write", password="WritePass123!")
    write_client[db_name].orders.insert_one({"order_id": "ORD-103", "item": "YubiKey 5C", "qty": 5, "status": "CONFIRMED"})
    print(f"  [ALLOWED] insert_one() on {db_name}.orders -> total orders={write_client[db_name].orders.count_documents({})}")

    try:
        write_client[db_name].products.find_one()
        print("  [ERROR] Read on products unexpectedly succeeded!")
    except OperationFailure as exc:
        print(f"  [DENIED AS EXPECTED] find_one() on {db_name}.products rejected -> code={exc.code} ({exc.details.get('codeName')})")

if __name__ == "__main__":
    main()