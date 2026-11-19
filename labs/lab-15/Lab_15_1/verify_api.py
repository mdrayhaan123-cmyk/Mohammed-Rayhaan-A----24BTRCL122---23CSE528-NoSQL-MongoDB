from fastapi.testclient import TestClient
from connection import get_client, get_db
from Lab_15_1.app import app, init_indexes, create_jwt_token, RATE_LIMIT_MAX

def main():
    print("=" * 78)
    print("LAB 15.1 & Activity 15.1: Multi-Tenant FastAPI, Rate Limiting & RBAC Verification")
    print("=" * 78)

    client = get_client()
    db = get_db(client)
    db.tasks.drop()
    db.rate_limits.drop()
    init_indexes(db)
    print("[INDEXES] Created compound index (tenant_id, created_at) & TTL rate_limits index (60s)")

    api = TestClient(app)

    # Mint JWT tokens for two isolated tenants and admin vs member roles
    alpha_admin = {"Authorization": f"Bearer {create_jwt_token('tenant_alpha', 'alice_admin', 'admin')}"}
    alpha_member_1 = {"Authorization": f"Bearer {create_jwt_token('tenant_alpha', 'bob_user', 'member')}"}
    alpha_member_2 = {"Authorization": f"Bearer {create_jwt_token('tenant_alpha', 'charlie_user', 'member')}"}
    beta_admin = {"Authorization": f"Bearer {create_jwt_token('tenant_beta', 'dave_admin', 'admin')}"}

    # 1. Create tasks under tenant_alpha (bob & charlie) and tenant_beta (dave)
    t_bob = api.post("/tasks/", json={"title": "Configure WAF", "description": "Edge rules", "priority": "high"}, headers=alpha_member_1).json()
    t_charlie = api.post("/tasks/", json={"title": "Rotate API Keys", "description": "Q4 audit", "priority": "medium"}, headers=alpha_member_2).json()
    t_beta = api.post("/tasks/", json={"title": "Beta Tenant Onboarding", "description": "SSO setup", "priority": "high"}, headers=beta_admin).json()
    print(f"[CRUD] Created 3 tasks across tenant_alpha ({t_bob['id']}, {t_charlie['id']}) and tenant_beta ({t_beta['id']})")

    # 2. Verify Tenant Isolation & RBAC Visibility
    bob_list = api.get("/tasks/", headers=alpha_member_1).json()
    alpha_admin_list = api.get("/tasks/", headers=alpha_admin).json()
    beta_admin_list = api.get("/tasks/", headers=beta_admin).json()

    assert len(bob_list) == 1 and bob_list[0]["owner_id"] == "bob_user"
    assert len(alpha_admin_list) == 2
    assert len(beta_admin_list) == 1 and beta_admin_list[0]["tenant_id"] == "tenant_beta"
    print(f"[ISOLATION & RBAC] bob (member) sees {len(bob_list)} task | alice (admin) sees {len(alpha_admin_list)} tenant_alpha tasks | dave sees {len(beta_admin_list)} tenant_beta task")

    # 3. Verify RBAC Ownership Enforcement (bob cannot update charlie's task; alice admin can)
    r_denied = api.patch(f"/tasks/{t_charlie['id']}", json={"status": "done"}, headers=alpha_member_1)
    assert r_denied.status_code == 403
    print(f"[RBAC BLOCKED] Regular user bob updating charlie's task -> HTTP {r_denied.status_code} ({r_denied.json()['detail']})")

    r_allowed = api.patch(f"/tasks/{t_charlie['id']}", json={"status": "done"}, headers=alpha_admin)
    assert r_allowed.status_code == 200 and r_allowed.json()["status"] == "done"
    print(f"[RBAC ALLOWED] Admin alice updating charlie's task -> HTTP {r_allowed.status_code} (status={r_allowed.json()['status']})")

    # 4. Verify MongoDB TTL Rate Limiter (burst requests until HTTP 429)
    print(f"\n--- Testing MongoDB Atomic TTL Rate Limiter (Max {RATE_LIMIT_MAX} req/min) ---")
    rate_user = {"Authorization": f"Bearer {create_jwt_token('tenant_gamma', 'burst_user', 'member')}"}
    statuses = []
    for _ in range(RATE_LIMIT_MAX + 2):
        resp = api.get("/tasks/", headers=rate_user)
        statuses.append(resp.status_code)
    assert statuses[-1] == 429
    print(f"  [RATE LIMIT TRIGGERED] Sequence of {len(statuses)} burst calls -> HTTP statuses={statuses}")

if __name__ == "__main__":
    main()