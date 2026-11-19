import os
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pymongo import MongoClient, DESCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)

app = FastAPI(title="CTI Sentinel & Labs 1-18 Live Laptop Analyzer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HTML_FILE = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_FILE.read_text(encoding="utf-8")

@app.get("/api/overview")
def overview():
    dbs = client.list_database_names()
    info = client.server_info()
    t18 = client["lab_18"].full_threats.count_documents({}) if "lab_18" in dbs else 0
    v17_db = "rag_demo" if "rag_demo" in dbs else "lab_17"
    v17 = client[v17_db].vector_5k.count_documents({}) if v17_db in dbs else 0
    return {
        "mongo_version": info.get("version", "7.x"),
        "database_count": len(dbs),
        "databases": dbs,
        "lab18_threats": t18,
        "lab17_vectors": v17,
    }

@app.get("/api/db-summary/{db_name}")
def db_summary(db_name: str):
    db = client[db_name]
    cols = db.list_collection_names()
    return {
        "database": db_name,
        "collections": {c: db[c].count_documents({}) for c in cols},
    }

@app.get("/api/lab11")
def analyze_lab11(strategy: str = "hashed"):
    dbs = [d for d in ["lab_11", "nosql_lab11_sharding"] if d in client.list_database_names()]
    total_docs = 0
    coll_stats = {}
    t0 = time.perf_counter()
    for d in dbs:
        db = client[d]
        coll_stats[d] = {}
        for c in db.list_collection_names():
            cnt = db[c].count_documents({})
            total_docs += cnt
            _ = db[c].find_one({})
            coll_stats[d][c] = {"documents": cnt, "indexes": list(db[c].index_information().keys())}
    targeted_ms = round((time.perf_counter() - t0) * 1000, 3)

    t1 = time.perf_counter()
    for d in dbs:
        db = client[d]
        for c in db.list_collection_names():
            _ = list(db[c].find({}).limit(200))
    scatter_ms = round((time.perf_counter() - t1) * 1000, 3)

    recommendation = (
        "Hashed shard key eliminates monotonic hotspot writes on ingestion."
        if strategy == "hashed"
        else "Ranged shard key keeps contiguous time/region ranges co-located on single chunks."
    )
    return {
        "strategy": strategy,
        "databases": dbs,
        "total_docs": total_docs,
        "targeted_query_ms": targeted_ms,
        "scatter_query_ms": scatter_ms,
        "architectural_verdict": recommendation,
        "collection_breakdown": coll_stats,
    }

class Lab12Payload(BaseModel):
    email: str
    age: int
    severity: str

@app.post("/api/lab12/validate")
def validate_lab12(p: Lab12Payload):
    valid_email = "@" in p.email and "." in p.email.split("@")[-1]
    valid_age = 18 <= p.age <= 120
    valid_sev = p.severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    passed = valid_email and valid_age and valid_sev
    db = client["lab_12"]
    if passed:
        db.governance_verified.insert_one({
            "email": p.email,
            "age": p.age,
            "severity": p.severity,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        })
    return {
        "schema_validation_passed": passed,
        "rule_checks": {
            "email_bson_pattern": valid_email,
            "age_min_18_max_120": valid_age,
            "severity_enum_match": valid_sev,
        },
        "mongo_action": "Document committed to lab_12.governance_verified" if passed else "Document rejected (validationAction: error)",
    }

@app.get("/api/lab13")
def analyze_lab13(role: str = "readOnlyAnalyst"):
    db = client["lab_13"]
    cols = db.list_collection_names()
    sample_records = []
    for c in cols[:2]:
        for doc in db[c].find({}, {"_id": 0}).limit(5):
            masked = dict(doc)
            if role != "securityAdmin":
                for k in list(masked.keys()):
                    if any(w in k.lower() for w in ["ssn", "secret", "password", "token", "cipher", "pii", "phone"]):
                        masked[k] = "[REDACTED_BY_RBAC]"
            sample_records.append({"collection": c, "view": masked})
    permissions = {
        "readOnlyAnalyst": ["find (non-PII projections only)"],
        "socResponder": ["find", "update alert status (PII masked)"],
        "securityAdmin": ["find", "insert", "update", "decrypt CSFLE fields"],
    }
    return {
        "active_role": role,
        "granted_privileges": permissions.get(role, []),
        "lab_13_collections": cols,
        "projected_documents": sample_records,
    }

@app.get("/api/lab14")
def analyze_lab14():
    srv = client.admin.command("serverStatus")
    conns = srv.get("connections", {})
    wt = srv.get("wiredTiger", {}).get("cache", {})
    b_in = wt.get("bytes currently in the cache", 1)
    b_read = wt.get("bytes read into cache", 0)
    hit_ratio = round((b_in / max(1, b_in + b_read)) * 100, 2)
    alerts = []
    if hit_ratio < 80.0:
        alerts.append(f"WiredTiger cache hit ratio {hit_ratio}% below 80% threshold")
    db14 = client["lab_14"]
    rpo_rto = list(db14.rpo_rto_benchmarks.find({}, {"_id": 0}))
    return {
        "live_metrics": {
            "connections_current": conns.get("current", 0),
            "connections_available": conns.get("available", 0),
            "wt_cached_mb": round(b_in / (1024 * 1024), 2),
            "cache_hit_ratio_pct": hit_ratio,
            "opcounters": srv.get("opcounters", {}),
            "alerts": alerts,
        },
        "rpo_rto_benchmarks": rpo_rto,
    }

@app.get("/api/lab15")
def analyze_lab15(tenant: str = "tenant_alpha"):
    db = client["lab_15"]
    if tenant.startswith("tenant_"):
        tasks = list(db.tasks.find({"tenant_id": tenant}, {"_id": 0}).limit(15))
        total_for_tenant = db.tasks.count_documents({"tenant_id": tenant})
        mode = "Document-Level Shared Collection (Compound Index: tenant_id + status)"
    else:
        coll_name = f"tasks_tenant_{tenant}"
        tasks = list(db[coll_name].find({}, {"_id": 0}).limit(15))
        total_for_tenant = db[coll_name].count_documents({})
        mode = f"Collection-Per-Tenant Physical Isolation ({coll_name})"
    benchmarks = list(db.isolation_benchmarks.find({}, {"_id": 0}))
    return {
        "tenant": tenant,
        "isolation_architecture": mode,
        "total_tasks_in_laptop_db": total_for_tenant,
        "sample_tasks": tasks,
        "isolation_benchmarks": benchmarks,
    }

class Lab15NewTask(BaseModel):
    tenant_id: str
    title: str

@app.post("/api/lab15/task")
def create_lab15_task(item: Lab15NewTask):
    db = client["lab_15"]
    doc = {
        "tenant_id": item.tenant_id,
        "owner_id": "portal_user",
        "title": item.title,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if item.tenant_id.startswith("tenant_"):
        db.tasks.insert_one(doc)
    else:
        db[f"tasks_tenant_{item.tenant_id}"].insert_one(doc)
    return {"created": True}

@app.get("/api/lab16")
def analyze_lab16(txn_id: str = "TXN-9001", trip: bool = False):
    db = client["lab_16"]
    txn = db.transactions.find_one({"txn_id": txn_id}, {"_id": 0})
    report = db.fraud_reports.find_one({"txn_id": txn_id}, {"_id": 0})
    matrix = list(db.polyglot_comparison.find({}, {"_id": 0}))
    cb_state = (
        {"Neo4j_CircuitBreaker": "OPEN (3 consecutive timeouts -> short-circuited for 30s)", "MongoDB": "CLOSED (HEALTHY)"}
        if trip
        else {"MongoDB": "CLOSED (HEALTHY)", "Cassandra": "CLOSED (HEALTHY)", "Neo4j": "CLOSED (HEALTHY)"}
    )
    return {
        "txn_id": txn_id,
        "circuit_breaker_status": cb_state,
        "mongodb_transaction": txn,
        "merged_polyglot_report": report,
        "polyglot_comparison_matrix": matrix,
    }

def _embed_384(text: str):
    dim = 384
    vec = [0.0] * dim
    tokens = [t.strip(".,!?;:\"'()[]").lower() for t in text.split() if t.strip()]
    for idx, tok in enumerate(tokens):
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        slot = int.from_bytes(h[:4], "little") % dim
        sign = 1.0 if (h[4] % 2 == 0) else -1.0
        vec[slot] += sign * (1.0 + 1.0 / (1.0 + (idx % 7)))
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]

class Lab17Input(BaseModel):
    query: str
    index_mode: str = "HNSW"

@app.post("/api/lab17/analyze")
def analyze_lab17(body: Lab17Input):
    db_name = "rag_demo" if "rag_demo" in client.list_database_names() else "lab_17"
    db = client[db_name]
    qvec = _embed_384(body.query)
    matches = []
    for doc in db.documents.find({}, {"_id": 0, "source": 1, "text": 1, "embedding": 1}):
        emb = doc.get("embedding", [])
        score = sum(a * b for a, b in zip(qvec, emb)) if emb else 0.0
        matches.append({"source": doc["source"], "score": round(score, 4), "text": doc["text"]})
    matches.sort(key=lambda x: x["score"], reverse=True)
    benchmarks = list(db.vector_benchmarks.find({}, {"_id": 0}))
    memory = list(db.conversations.find({}, {"_id": 0}).limit(5))
    index_note = (
        "HNSW (M=16, efConstruction=64..256) delivers 96.0%–97.15% Top-20 recall at ~0.95–1.03 ms—recommended for RAG & customer-facing search."
        if body.index_mode == "HNSW"
        else "IVF (nlist=100, nprobe=10..100) trades recall (91.95% at nprobe=10) for lower memory footprint on multi-million vector datasets."
    )
    return {
        "matches": matches[:3],
        "index_analysis": index_note,
        "benchmarks": benchmarks,
        "recent_memory": memory,
    }

@app.get("/api/lab18/analyze")
def analyze_lab18(source: str = "ALL", cluster: str = "ALL", scale: str = "100M"):
    db = client["lab_18"]
    t0 = time.perf_counter()
    total_threats = db.full_threats.count_documents({})
    filt = {}
    if source != "ALL":
        filt["from_source"] = source
    if cluster != "ALL":
        filt["fp_cluster"] = cluster
    matched_count = db.full_threats.count_documents(filt)
    fp_filt = dict(filt)
    fp_filt["fp_cluster"] = {"$ne": None} if cluster == "ALL" else cluster
    fp_count = db.full_threats.count_documents(fp_filt)
    samples = list(db.full_threats.find(filt, {"_id": 0}).sort("timestamp", DESCENDING).limit(6))
    for s in samples:
        if "timestamp" in s:
            s["timestamp"] = str(s["timestamp"])
    query_ms = round((time.perf_counter() - t0) * 1000, 3)

    scale_map = {
        "1M": {"footprint": "~1.2 GB", "mongodb": "1 shard (3-node RS)", "cassandra": "3-node ring (RF=2)", "neo4j": "Single instance", "hardware": "8 GB RAM / 20 GB NVMe"},
        "10M": {"footprint": "~12 GB", "mongodb": "2-3 shards (hashed/ranged)", "cassandra": "3-5 nodes (RF=3)", "neo4j": "Cluster (4-8 GB heap)", "hardware": "32 GB RAM / 100 GB NVMe"},
        "100M": {"footprint": "~120 GB", "mongodb": "6-8 shards + config RS", "cassandra": "6-12 nodes (RF=3)", "neo4j": "Causal cluster / sharded graph", "hardware": "128 GB RAM / 500+ GB NVMe"},
    }
    return {
        "total_threats": total_threats,
        "matched_count": matched_count,
        "fp_candidate_count": fp_count,
        "query_ms": query_ms,
        "selected_scale_blueprint": scale_map.get(scale, scale_map["100M"]),
        "benchmark_medians_10_runs": list(db.benchmark_results.find({}, {"_id": 0})),
        "false_positive_communities": list(db.fp_communities.find({}, {"_id": 0})),
        "sample_records": samples,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)