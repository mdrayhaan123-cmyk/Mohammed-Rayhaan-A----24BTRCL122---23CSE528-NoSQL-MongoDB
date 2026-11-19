import os
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://host.docker.internal:27017/?maxPoolSize=10")

def get_mongo_client(retries: int = 20, delay: float = 2.0):
    uri = get_mongo_uri()
    last_err = None
    for _ in range(retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000, maxPoolSize=10)
            client.admin.command("ping")
            return client
        except PyMongoError as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to MongoDB at {uri}: {last_err}")

def get_db(client=None):
    if client is None:
        client = get_mongo_client()
    return client[os.getenv("DB_NAME", "lab_16")]

def connect_cassandra(retries: int = 25, delay: float = 3.0):
    host = os.getenv("CASSANDRA_HOST", "").strip()
    if not host:
        return None, None
    from cassandra.cluster import Cluster
    last_err = None
    for _ in range(retries):
        try:
            cluster = Cluster([host], port=int(os.getenv("CASSANDRA_PORT", "9042")), executor_threads=4)
            session = cluster.connect()
            return cluster, session
        except Exception as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to Cassandra at {host}: {last_err}")

def connect_neo4j(retries: int = 25, delay: float = 2.0):
    uri = os.getenv("NEO4J_URI", "").strip()
    if not uri:
        return None
    from neo4j import GraphDatabase
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASS", "Neo4jPass123!")
    last_err = None
    for _ in range(retries):
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password), max_connection_pool_size=10)
            driver.verify_connectivity()
            return driver
        except Exception as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to Neo4j at {uri}: {last_err}")