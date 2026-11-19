import os
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def build_client(username=None, password=None, auth_source="admin", use_tls=None, timeout_ms=5000):
    host = os.getenv("MONGO_HOST", "host.docker.internal")
    port = int(os.getenv("MONGO_PORT", "27017"))
    if use_tls is None:
        use_tls = os.getenv("MONGO_TLS", "false").lower() == "true"

    kwargs = {
        "host": host,
        "port": port,
        "serverSelectionTimeoutMS": timeout_ms,
        "directConnection": True,
    }
    if username and password:
        kwargs["username"] = username
        kwargs["password"] = password
        kwargs["authSource"] = auth_source

    if use_tls:
        cert_dir = os.getenv("CERT_DIR", "/certs")
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = os.path.join(cert_dir, "ca.crt")
        kwargs["tlsCertificateKeyFile"] = os.path.join(cert_dir, "client.pem")

    return MongoClient(**kwargs)

def wait_for_mongo(retries: int = 15, delay: float = 2.0):
    admin_user = os.getenv("MONGO_ADMIN_USER", "")
    admin_pass = os.getenv("MONGO_ADMIN_PASS", "")
    last_err = None
    for _ in range(retries):
        try:
            client = build_client(username=admin_user or None, password=admin_pass or None)
            client.admin.command("ping")
            return client
        except PyMongoError as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to MongoDB: {last_err}")