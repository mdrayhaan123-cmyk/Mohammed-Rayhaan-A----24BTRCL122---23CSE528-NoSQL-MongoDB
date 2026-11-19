import os
import time
from datetime import datetime, timezone
from tabulate import tabulate
from connection import get_mongo_client, get_db, connect_cassandra, connect_neo4j

class CircuitBreaker:
    """Trips after 3 consecutive backend failures and retries after 30 seconds."""
    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.opened_at = None

    def allow_request(self) -> bool:
        if self.opened_at is None:
            return True
        if (time.monotonic() - self.opened_at) >= self.recovery_timeout:
            self.opened_at = None
            self.failure_count = 0
            return True
        return False

    def record_success(self):
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self):
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold and self.opened_at is None:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        return "OPEN (SKIPPED)" if not self.allow_request() else "CLOSED (HEALTHY)"


class FraudQueryService:
    def __init__(self, mongo_client=None, cassandra_session=None, neo4j_driver=None, db_name: str = None):
        self.mongo_client = mongo_client or get_mongo_client()
        self.db = self.mongo_client[db_name or os.getenv("DB_NAME", "lab_16")]
        self.cassandra_session = cassandra_session
        self.neo4j_driver = neo4j_driver

        self.cb_mongo = CircuitBreaker("MongoDB")
        self.cb_cassandra = CircuitBreaker("Cassandra")
        self.cb_neo4j = CircuitBreaker("Neo4j")

    def get_transaction(self, txn_id: str):
        if not self.cb_mongo.allow_request():
            return {"status": "circuit_open", "backend": "MongoDB"}
        try:
            doc = self.db.transactions.find_one({"txn_id": txn_id}, {"_id": 0})
            self.cb_mongo.record_success()
            return doc
        except Exception as exc:
            self.cb_mongo.record_failure()
            return {"status": "error", "backend": "MongoDB", "detail": str(exc)}

    def get_user_profile(self, user_id: str, limit: int = 10):
        if not self.cb_cassandra.allow_request():
            return [{"status": "circuit_open", "backend": "Cassandra"}]
        if self.cassandra_session is None:
            return []
        try:
            rows = self.cassandra_session.execute(
                "SELECT user_id, event_time, txn_id, amount, channel FROM fraud_ks.user_profiles WHERE user_id = %s LIMIT %s",
                (user_id, limit),
            )
            self.cb_cassandra.record_success()
            return [
                {
                    "user_id": r.user_id,
                    "event_time": str(r.event_time),
                    "txn_id": r.txn_id,
                    "amount": float(r.amount),
                    "channel": r.channel,
                }
                for r in rows
            ]
        except Exception as exc:
            self.cb_cassandra.record_failure()
            return [{"status": "error", "backend": "Cassandra", "detail": str(exc)}]

    def detect_fraud_rings(self, user_id: str, max_hops: int = 3):
        if not self.cb_neo4j.allow_request():
            return [{"status": "circuit_open", "backend": "Neo4j"}]
        if self.neo4j_driver is None:
            return []
        try:
            cypher = f"""
                MATCH path = (u:User {{id: $uid}})-[:TRANSFERRED_TO*1..{int(max_hops)}]-(connected:User)
                WHERE connected.id <> $uid
                RETURN [n IN nodes(path) | n.id] AS ring_path, length(path) AS hops
                LIMIT 50
            """
            with self.neo4j_driver.session() as session:
                records = session.run(cypher, uid=user_id)
                rings = [{"ring_path": rec["ring_path"], "hops": rec["hops"]} for rec in records]
            self.cb_neo4j.record_success()
            return rings
        except Exception as exc:
            self.cb_neo4j.record_failure()
            return [{"status": "error", "backend": "Neo4j", "detail": str(exc)}]

    def analyze_fraud_case(self, txn_id: str, user_id: str, max_hops: int = 3) -> dict:
        t0 = time.perf_counter()
        txn = self.get_transaction(txn_id)
        mongo_ms = round((time.perf_counter() - t0) * 1000, 3)

        t1 = time.perf_counter()
        events = self.get_user_profile(user_id)
        cass_ms = round((time.perf_counter() - t1) * 1000, 3)

        t2 = time.perf_counter()
        rings = self.detect_fraud_rings(user_id, max_hops=max_hops)
        neo_ms = round((time.perf_counter() - t2) * 1000, 3)

        return {
            "txn_id": txn_id,
            "user_id": user_id,
            "transaction": txn,
            "recent_events": events,
            "fraud_rings": rings,
            "latencies_ms": {
                "mongodb_ms": mongo_ms,
                "cassandra_ms": cass_ms,
                "neo4j_ms": neo_ms,
            },
        }


def run_integration_and_latency_benchmark():
    print("=" * 78)
    print("LAB 16.2: FraudQueryService Polyglot Integration & Latency Profiling")
    print("=" * 78)

    mongo_client = get_mongo_client()
    db = get_db(mongo_client)

    # Seed MongoDB transactions
    db.transactions.drop()
    db.transactions.insert_many([
        {
            "txn_id": "TXN-9001",
            "user_id": "USR-101",
            "amount": 9850.00,
            "merchant": "Offshore Wire X",
            "risk_score": 0.94,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        {
            "txn_id": "TXN-9002",
            "user_id": "USR-102",
            "amount": 120.50,
            "merchant": "Cloud Hosting Ltd",
            "risk_score": 0.12,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    ])

    cass_cluster, cass_session = connect_cassandra()
    if cass_session is not None:
        cass_session.execute("""
            CREATE KEYSPACE IF NOT EXISTS fraud_ks
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
        """)
        cass_session.execute("DROP TABLE IF EXISTS fraud_ks.user_profiles")
        cass_session.execute("""
            CREATE TABLE fraud_ks.user_profiles (
                user_id text,
                event_time timestamp,
                txn_id text,
                amount double,
                channel text,
                PRIMARY KEY ((user_id), event_time)
            ) WITH CLUSTERING ORDER BY (event_time DESC)
        """)
        cass_session.execute(
            "INSERT INTO fraud_ks.user_profiles (user_id, event_time, txn_id, amount, channel) VALUES (%s, %s, %s, %s, %s)",
            ("USR-101", datetime.now(timezone.utc), "TXN-9001", 9850.00, "API_WIRE"),
        )

    neo_driver = connect_neo4j()
    if neo_driver is not None:
        with neo_driver.session() as session:
            session.run("MATCH (n:User) DETACH DELETE n")
            session.run("""
                CREATE (u1:User {id: 'USR-101', name: 'Originator'}),
                       (u2:User {id: 'USR-102', name: 'Mule-A'}),
                       (u3:User {id: 'USR-103', name: 'Mule-B'}),
                       (u1)-[:TRANSFERRED_TO {amount: 9850}]->(u2),
                       (u2)-[:TRANSFERRED_TO {amount: 9500}]->(u3),
                       (u3)-[:TRANSFERRED_TO {amount: 9200}]->(u1)
            """)

    service = FraudQueryService(
        mongo_client=mongo_client,
        cassandra_session=cass_session,
        neo4j_driver=neo_driver,
    )

    report = service.analyze_fraud_case("TXN-9001", "USR-101", max_hops=3)
    print(f"[MERGED FRAUD REPORT] txn_id={report['txn_id']} | risk_score={report['transaction']['risk_score']}")
    print(f"  - MongoDB Transaction : {report['transaction']}")
    print(f"  - Cassandra Events    : {len(report['recent_events'])} time-ordered event(s)")
    print(f"  - Neo4j Fraud Rings   : {len(report['fraud_rings'])} multi-hop path(s) -> {report['fraud_rings'][:2]}")

    lat_rows = [
        ["MongoDB (get_transaction)", f"{report['latencies_ms']['mongodb_ms']} ms", "2 - 5 ms", "Flexible BSON lookup by indexed txn_id"],
        ["Cassandra (get_user_profile)", f"{report['latencies_ms']['cassandra_ms']} ms", "3 - 8 ms", "Partition key seek + descending clustering"],
        ["Neo4j (detect_fraud_rings)", f"{report['latencies_ms']['neo4j_ms']} ms", "10 - 500 ms", "Variable-length 1..3 hop graph traversal"],
    ]
    print("\n--- Polyglot Latency Measurement ---")
    print(tabulate(lat_rows, headers=["Service Method", "Measured Latency", "Reference Range", "Access Pattern"], tablefmt="grid"))

    # Persist merged fraud report into lab_16.fraud_reports for Compass inspection
    db.fraud_reports.drop()
    db.fraud_reports.insert_one(report)

    if cass_cluster:
        cass_cluster.shutdown()
    if neo_driver:
        neo_driver.close()


if __name__ == "__main__":
    run_integration_and_latency_benchmark()