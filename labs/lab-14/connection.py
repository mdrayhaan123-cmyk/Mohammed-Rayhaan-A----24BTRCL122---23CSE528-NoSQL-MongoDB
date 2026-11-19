import os
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://host.docker.internal:27017/")

def get_client(retries: int = 20, delay: float = 2.0):
    uri = get_mongo_uri()
    last_err = None
    for _ in range(retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000, retryReads=True, retryWrites=True)
            client.admin.command("ping")
            return client
        except PyMongoError as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to MongoDB at {uri}: {last_err}")

def get_db(client=None):
    if client is None:
        client = get_client()
    return client[os.getenv("DB_NAME", "lab_14")]