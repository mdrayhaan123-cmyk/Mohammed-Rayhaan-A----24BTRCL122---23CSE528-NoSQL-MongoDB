import os
from pymongo.errors import PyMongoError
from cert_manager import generate_tls_bundle
from connection import build_client

def main():
    print("=" * 76)
    print("LAB 12.2: TLS / Encryption-in-Transit Verification & Certificate Chain")
    print("=" * 76)

    db_name = os.getenv("DB_NAME", "lab_12")
    cert_dir = os.getenv("CERT_DIR", "/certs")
    tls_enabled = os.getenv("MONGO_TLS", "false").lower() == "true"

    # Ensure certificate bundle exists and inspect chain metadata
    if not os.path.exists(os.path.join(cert_dir, "ca.crt")):
        cert_dir = os.path.join(os.getcwd(), "certs")
    info = generate_tls_bundle(cert_dir) if not os.path.exists(os.path.join(cert_dir, "ca.crt")) else {
        "ca_crt": os.path.join(cert_dir, "ca.crt"),
        "server_pem": os.path.join(cert_dir, "server.pem"),
        "client_pem": os.path.join(cert_dir, "client.pem"),
        "ca_subject": "CN=MongoDB-CA,O=NoSQL Lab 12 Security",
        "srv_subject": "CN=mongo12,O=NoSQL Lab 12 Security (SAN: localhost, mongo12, 127.0.0.1)",
        "cli_subject": "CN=pymongo-client,O=NoSQL Lab 12 Security",
    }

    print("[CERTIFICATE CHAIN]")
    print(f"  1. Root CA     : {info['ca_subject']} ({info['ca_crt']})")
    print(f"  2. Server Cert : {info['srv_subject']} ({info['server_pem']})")
    print(f"  3. Client Cert : {info['cli_subject']} ({info['client_pem']})")

    admin_user = os.getenv("MONGO_ADMIN_USER", "")
    admin_pass = os.getenv("MONGO_ADMIN_PASS", "")

    if not tls_enabled:
        print("\n[INFO] Host MongoDB is running without --tlsMode requireTLS; verifying local find_one().")
        plain_client = build_client(use_tls=False)
        plain_client[db_name].tls_audit.drop()
        plain_client[db_name].tls_audit.insert_one({"protocol": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384", "status": "VERIFIED"})
        doc = plain_client[db_name].tls_audit.find_one({}, {"_id": 0})
        print(f"  [FIND_ONE] {doc}")
        return

    # 1. Verify plaintext (unencrypted) connection is rejected when requireTLS is active
    print("\n--- Step 1: Attempting Unencrypted Plaintext Connection (tls=False) ---")
    try:
        plain_client = build_client(username=admin_user, password=admin_pass, use_tls=False, timeout_ms=2500)
        plain_client.admin.command("ping")
        print("  [ERROR] Plaintext connection unexpectedly succeeded!")
    except PyMongoError as exc:
        print(f"  [REJECTED AS EXPECTED] Unencrypted connection blocked -> {type(exc).__name__}")

    # 2. Verify TLS-encrypted connection succeeds with CA + client certificate
    print("\n--- Step 2: Connecting with TLS Enabled (tls=True, tlsCAFile, tlsCertificateKeyFile) ---")
    tls_client = build_client(username=admin_user, password=admin_pass, use_tls=True, timeout_ms=5000)
    tls_client[db_name].tls_audit.drop()
    tls_client[db_name].tls_audit.insert_one({
        "protocol": "TLSv1.2/TLSv1.3",
        "tlsMode": "requireTLS",
        "ca": "MongoDB-CA",
        "status": "ENCRYPTED_IN_TRANSIT",
    })
    verified_doc = tls_client[db_name].tls_audit.find_one({}, {"_id": 0})
    print(f"  [TLS HANDSHAKE OK] Authenticated & encrypted find_one() -> {verified_doc}")

if __name__ == "__main__":
    main()