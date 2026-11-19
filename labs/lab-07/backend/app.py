"""FastAPI Backend for Cyber Threat Intelligence (CTI) Platform (Lab 7.1 & 7.2)."""

import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from config.connection import get_db
from backend.seed_cti_data import seed_all

app = FastAPI(title="Cyber Threat Intelligence Platform (Lab 7)")


class ClassifyRequest(BaseModel):
    severity: str
    is_actual_threat: bool
    category: Optional[str] = None


@app.on_event("startup")
def startup_seed():
    db = get_db("lab_7")
    if db["threat_reports"].count_documents({}) == 0:
        seed_all()


@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(ROOT_DIR, "frontend", "index.html"))


@app.get("/api/threats")
def list_threats(
    q: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    actual_threat: Optional[str] = None,
):
    db = get_db("lab_7")
    query: dict = {}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"summary": {"$regex": q, "$options": "i"}},
            {"vendor": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    if category and category != "All":
        query["category"] = category
    if severity and severity != "All":
        query["severity"] = severity
    if actual_threat in ("true", "false"):
        query["is_actual_threat"] = (actual_threat == "true")

    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "threat_sources",
                "localField": "source_id",
                "foreignField": "source_id",
                "as": "source_info",
            }
        },
        {"$project": {"_id": 0, "source_info._id": 0}},
    ]
    reports = list(db["threat_reports"].aggregate(pipeline))
    return {"count": len(reports), "reports": reports}


@app.post("/api/threats/{report_id}/classify")
def classify_threat(report_id: str, payload: ClassifyRequest):
    db = get_db("lab_7")
    update_fields = {
        "severity": payload.severity,
        "is_actual_threat": payload.is_actual_threat,
    }
    if payload.category:
        update_fields["category"] = payload.category
    res = db["threat_reports"].update_one({"report_id": report_id}, {"$set": update_fields})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    updated = db["threat_reports"].find_one({"report_id": report_id}, {"_id": 0})
    return {"status": "updated", "report": updated}


@app.get("/api/schema-analysis")
def schema_analysis():
    db = get_db("lab_7")
    pipeline = [
        {"$project": {"_id": 0, "report_id": 1, "title": 1, "ioc_count": {"$size": {"$ifNull": ["$iocs", []]}}, "bson_bytes": {"$bsonSize": "$$ROOT"}}}
    ]
    sizes = []
    for doc in db["threat_reports"].aggregate(pipeline):
        bsize = doc["bson_bytes"]
        sizes.append({
            "report_id": doc["report_id"],
            "title": doc["title"],
            "ioc_count": doc["ioc_count"],
            "bson_bytes": bsize,
            "pct_of_16mb": round((bsize / (16 * 1024 * 1024)) * 100, 5),
        })
    avg_bytes = round(sum(s["bson_bytes"] for s in sizes) / len(sizes), 2) if sizes else 0
    return {
        "database": "lab_7",
        "avg_bson_bytes": avg_bytes,
        "max_limit_bytes": 16 * 1024 * 1024,
        "documents": sizes,
    }


@app.get("/api/cache-status")
def cache_status():
    db = get_db("lab_7")
    status = db.command("serverStatus")
    cache = status.get("wiredTiger", {}).get("cache", {})
    max_bytes = cache.get("maximum bytes configured", 0)
    used_bytes = cache.get("bytes currently in the cache", 0)
    pages_read = cache.get("pages read into cache", 0)
    pages_evicted = cache.get("eviction pages evicted by application threads", 0)
    hit_ratio = round(max(0.0, 1.0 - (pages_evicted / pages_read)) * 100, 2) if pages_read else 100.0
    return {
        "max_cache_mb": round(max_bytes / (1024 * 1024), 2),
        "used_cache_mb": round(used_bytes / (1024 * 1024), 2),
        "pct_cache_used": round((used_bytes / max_bytes) * 100, 2) if max_bytes else 0,
        "pages_read": pages_read,
        "pages_evicted": pages_evicted,
        "approx_hit_ratio_pct": hit_ratio,
        "working_set_docs": db["working_set_docs"].count_documents({}),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
