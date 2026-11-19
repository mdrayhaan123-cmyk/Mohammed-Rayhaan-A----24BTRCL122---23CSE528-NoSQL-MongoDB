import os
from datetime import datetime, timezone
from typing import Optional
import jwt
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import ASCENDING, ReturnDocument
from connection import get_client, get_db

JWT_SECRET = os.getenv("JWT_SECRET", "nosql-lab15-super-secret-key-2026")
JWT_ALGO = "HS256"
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "10"))

app = FastAPI(title="TaskTracker Multi-Tenant SaaS API (Lab 15.1)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_indexes(db):
    db.tasks.create_index([("tenant_id", ASCENDING), ("created_at", ASCENDING)])
    db.rate_limits.create_index([("window_start", ASCENDING)], expireAfterSeconds=60)
    db.rate_limits.create_index([("tenant_id", ASCENDING), ("user_id", ASCENDING), ("window_key", ASCENDING)], unique=True)

def create_jwt_token(tenant_id: str, user_id: str, role: str) -> str:
    payload = {"tenant_id": tenant_id, "user_id": user_id, "role": role}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Bearer JWT token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid JWT token: {exc}")
    if "tenant_id" not in claims or "user_id" not in claims:
        raise HTTPException(status_code=401, detail="JWT missing tenant_id or user_id")
    claims.setdefault("role", "member")
    return claims

def enforce_rate_limit(user: dict = Depends(get_current_user)):
    db = get_db()
    now = datetime.now(timezone.utc)
    window_key = now.strftime("%Y%m%d%H%M")
    doc = db.rate_limits.find_one_and_update(
        {
            "tenant_id": user["tenant_id"],
            "user_id": user["user_id"],
            "window_key": window_key,
        },
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"window_start": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if doc["count"] > RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({RATE_LIMIT_MAX} req/min) for tenant={user['tenant_id']}",
        )
    return user

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

def _serialize_task(doc: dict) -> dict:
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    return out

@app.post("/tasks/")
def create_task(task: TaskCreate, user: dict = Depends(enforce_rate_limit)):
    db = get_db()
    doc = {
        "tenant_id": user["tenant_id"],
        "owner_id": user["user_id"],
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = db.tasks.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc

@app.get("/tasks/")
def list_tasks(user: dict = Depends(enforce_rate_limit)):
    db = get_db()
    query = {"tenant_id": user["tenant_id"]}
    # RBAC: admin sees all tenant tasks; regular member sees only own tasks
    if user["role"] != "admin":
        query["owner_id"] = user["user_id"]
    return [_serialize_task(t) for t in db.tasks.find(query)]

@app.patch("/tasks/{task_id}")
def update_task(task_id: str, patch: TaskUpdate, user: dict = Depends(enforce_rate_limit)):
    db = get_db()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id")
    existing = db.tasks.find_one({"_id": ObjectId(task_id), "tenant_id": user["tenant_id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found in tenant scope")
    if user["role"] != "admin" and existing.get("owner_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="RBAC Denied: regular users can only manage their own tasks")

    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    if updates:
        db.tasks.update_one({"_id": ObjectId(task_id), "tenant_id": user["tenant_id"]}, {"$set": updates})
    updated = db.tasks.find_one({"_id": ObjectId(task_id), "tenant_id": user["tenant_id"]})
    return _serialize_task(updated)

@app.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: dict = Depends(enforce_rate_limit)):
    db = get_db()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id")
    existing = db.tasks.find_one({"_id": ObjectId(task_id), "tenant_id": user["tenant_id"]})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found in tenant scope")
    if user["role"] != "admin" and existing.get("owner_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="RBAC Denied: regular users can only delete their own tasks")

    db.tasks.delete_one({"_id": ObjectId(task_id), "tenant_id": user["tenant_id"]})
    return {"deleted": True, "id": task_id, "tenant_id": user["tenant_id"]}