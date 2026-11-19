import os
from pymongo.errors import OperationFailure
from connection import wait_for_mongo, build_client

def main():
    print("=" * 76)
    print("LAB 12.1 (Try It Yourself): Field-Level Redaction via MongoDB Views")
    print("=" * 76)

    db_name = os.getenv("DB_NAME", "lab_12")
    admin_user = os.getenv("MONGO_ADMIN_USER", "")

    admin_client = wait_for_mongo()
    db = admin_client[db_name]
    admin_db = admin_client["admin"]

    # Create base collection with sensitive salary field + redacted view excluding salary
    db.employees_public.drop()
    db.employees.drop()
    db.employees.insert_many([
        {"emp_id": "EMP-01", "name": "Alice Mercer", "department": "Security Ops", "salary": 145000},
        {"emp_id": "EMP-02", "name": "Bob Vance", "department": "Cloud Infra", "salary": 132000},
    ])
    db.create_collection(
        "employees_public",
        viewOn="employees",
        pipeline=[{"$project": {"salary": 0, "_id": 0}}],
    )
    print(f"[VIEW CREATED] '{db_name}.employees_public' excludes 'salary' via $project")

    if not admin_user:
        sample_public = list(db.employees_public.find({}))
        print(f"  [PUBLIC VIEW PREVIEW] {sample_public}")
        return

    for role_name in ("hrFullRole", "staffViewOnlyRole"):
        try:
            admin_db.command("dropRole", role_name)
        except OperationFailure:
            pass

    admin_db.command(
        "createRole",
        "hrFullRole",
        privileges=[{"resource": {"db": db_name, "collection": "employees"}, "actions": ["find"]}],
        roles=[],
    )
    admin_db.command(
        "createRole",
        "staffViewOnlyRole",
        privileges=[{"resource": {"db": db_name, "collection": "employees_public"}, "actions": ["find"]}],
        roles=[],
    )

    for u in ("hr_user", "staff_user"):
        try:
            admin_db.command("dropUser", u)
        except OperationFailure:
            pass

    admin_db.command("createUser", "hr_user", pwd="HrPass123!", roles=[{"role": "hrFullRole", "db": "admin"}])
    admin_db.command("createUser", "staff_user", pwd="StaffPass123!", roles=[{"role": "staffViewOnlyRole", "db": "admin"}])

    # Staff user queries redacted view -> succeeds without salary
    staff_client = build_client(username="staff_user", password="StaffPass123!")
    redacted_docs = list(staff_client[db_name].employees_public.find({}))
    print(f"  [STAFF -> employees_public] {redacted_docs}")

    # Staff user attempts direct query on employees -> denied
    try:
        staff_client[db_name].employees.find_one()
    except OperationFailure as exc:
        print(f"  [STAFF -> employees DIRECT] Blocked -> code={exc.code} ({exc.details.get('codeName')})")

    # HR user queries base employees collection -> sees salary
    hr_client = build_client(username="hr_user", password="HrPass123!")
    hr_docs = list(hr_client[db_name].employees.find({}, {"_id": 0}))
    print(f"  [HR    -> employees DIRECT] {hr_docs}")

if __name__ == "__main__":
    main()