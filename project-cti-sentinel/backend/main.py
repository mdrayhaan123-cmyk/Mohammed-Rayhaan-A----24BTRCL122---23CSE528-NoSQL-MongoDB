from dotenv import load_dotenv
load_dotenv()
from backend.gemini_client import ask_gemini_cti, has_gemini_key
import asyncio
import json
import os
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pymongo import MongoClient

from backend.ingest import embed_text, seed_knowledge_base
from backend.scanner_daemon import apply_confirmed_mitigation, detect_host_platform, run_platform_vulnerability_scan

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "llm_chat_app")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", "45"))

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = mongo_client[MONGO_DB]
knowledge_col = db["knowledge"]
sessions_col = db["sessions"]
findings_col = db["scan_findings"]

METRICS = {"total_requests": 0, "chat_requests": 0, "avg_latency_ms": 0.0, "llm_mode_used": "rag-synthesizer"}
RATE_BUCKET = defaultdict(list)

async def background_scanner_loop():
    while True:
        try:
            run_platform_vulnerability_scan(db)
        except Exception:
            pass
        await asyncio.sleep(SCAN_INTERVAL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_knowledge_base(db)
    run_platform_vulnerability_scan(db)
    task = asyncio.create_task(background_scanner_loop())
    yield
    task.cancel()
    mongo_client.close()

app = FastAPI(title="CTI Sentinel LLM Threat Intelligence & Remediation API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def monitor_and_rate_limit(request: Request, call_next):
    client_ip = request.client.host if request.client else "local"
    now = time.time()
    RATE_BUCKET[client_ip] = [t for t in RATE_BUCKET[client_ip] if now - t < 60]
    if request.url.path == "/chat" and len(RATE_BUCKET[client_ip]) >= 30:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded (30 chat requests/min)"})
    if request.url.path == "/chat":
        RATE_BUCKET[client_ip].append(now)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    METRICS["total_requests"] += 1
    n = METRICS["total_requests"]
    METRICS["avg_latency_ms"] = round(((METRICS["avg_latency_ms"] * (n - 1)) + elapsed_ms) / n, 2)
    return response

def retrieve_context(query: str, platform_filter: str = "ALL", lifecycle_filter: str = "ALL", n_results: int = 3) -> list[dict]:
    q_vec = np.array(embed_text(query), dtype=np.float32)
    mongo_filter = {}
    if platform_filter and platform_filter != "ALL":
        mongo_filter["platform"] = platform_filter
    if lifecycle_filter and lifecycle_filter != "ALL":
        mongo_filter["lifecycle"] = lifecycle_filter

    docs = list(knowledge_col.find(mongo_filter, {"_id": 0}))
    if not docs:
        docs = list(knowledge_col.find({}, {"_id": 0}))

    scored = []
    for d in docs:
        emb = d.get("embedding")
        if emb:
            d_vec = np.array(emb, dtype=np.float32)
            sim = float(np.dot(q_vec, d_vec))
        else:
            sim = 0.5
        scored.append((sim, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**item[1], "similarity": round(item[0], 4)} for item in scored[:n_results]]

def get_history(session_id: str, n: int = 5) -> list[dict]:
    msgs = list(sessions_col.find({"session_id": session_id}, {"_id": 0}).sort("timestamp", -1).limit(n * 2))[::-1]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]

def generate_llm_response(user_msg: str, platform_filter: str, lifecycle_filter: str, chunks: list[dict], history: list[dict]) -> tuple[str, str]:
    if has_gemini_key():
        try:
            return ask_gemini_cti(user_msg, chunks, history, platform_filter, lifecycle_filter)
        except Exception:
            pass

    q = (user_msg or "").strip()
    ql = q.lower()

    if any(w in ql for w in ("what can you do", "what can u do", "capabilities", "help", "features")):
        return (
            "I can answer general questions, explain concepts, help with coding/technical topics, and query your CTI Sentinel MongoDB knowledge base & scanner findings.\n\n"
            "- **General Q&A & Explanations:** Ask any everyday, academic, or technical question.\n"
            "- **Threat & CVE Lookup:** Filter by platform (`Windows`, `Linux`, `macOS`, `Android`, `iOS`) and lifecycle (`Anticipated`, `Active`, `Evolving`, `Resolved`).\n"
            "- **Host Scan & Mitigation:** Run system scans and confirm fixes (e.g., `confirm VULN-WIN-101`) with MongoDB persistence."
        ), "cti-assistant"

    if any(w in ql for w in ("unresolved", "free from threat", "any risk", "open risk", "pending")):
        open_items = [c for c in (chunks or []) if str(c.get("lifecycle", "")).lower() != "resolved"]
        if open_items:
            out = ["Here are the non-resolved items matching your current filter:"]
            for c in open_items[:4]:
                out.append(f"- **{c.get('title')}** (`{c.get('cve')}`, **{c.get('lifecycle')}**) — `{c.get('remediation_cmd', 'Apply patch')}`")
            return "\n".join(out), "cti-assistant"
        return (
            "All currently retrieved items in your active view are marked **Resolved**, though this only reflects audited scanner rules and retrieved playbooks—new or unscanned threats can still emerge."
        ), "cti-assistant"

    cti_keywords = ("cve", "vuln", "threat", "malware", "firewall", "port", "exploit", "scan", "remediation", "mitigation", "playbook", "windows", "linux", "macos", "android", "ios")
    if any(w in ql for w in cti_keywords) and chunks:
        out = [f"### CTI Matches ({platform_filter} | {lifecycle_filter})"]
        for c in chunks[:3]:
            out.append(
                f"- **{c.get('title', 'Finding')}** (`{c.get('cve', 'N/A')}` | **{c.get('severity', 'N/A')}** | **{c.get('lifecycle', 'N/A')}**)\n"
                f"  - {c.get('text', '')}\n"
                f"  - **Action:** `{c.get('remediation_cmd', 'Apply security update')}`"
            )
        return "\n\n".join(out), "mongodb-rag-synthesizer"

    recent_context = ""
    if history:
        prior_user = [m.get("content", "") for m in history if m.get("role") == "user" and m.get("content", "").strip() != q]
        if prior_user:
            recent_context = f" (Continuing from your earlier topic: *\"{prior_user[-1][:80]}\"*)"

    return (
        f"You asked: **\"{q}\"**{recent_context}.\n\n"
        "The external Gemini endpoint timed out on this request, so I am running in local assistant mode without pre-canned CVE templates. "
        "Please retry in a moment for full generative LLM answers, or ask a specific question about your MongoDB threats, CVEs, ports, or remediation commands."
    ), "local-assistant"

@app.get("/")
def serve_frontend():
    front_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(front_path):
        return FileResponse(front_path)
    return {"message": "CTI Sentinel LLM Backend Running", "docs": "/docs"}

@app.get("/health")
def health():
    try:
        mongo_client.admin.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {
        "status": "healthy" if mongo_ok else "degraded",
        "mongodb": "connected" if mongo_ok else "unreachable",
        "host_platform": detect_host_platform(),
        "knowledge_chunks": knowledge_col.count_documents({}),
        "pending_vulnerabilities": findings_col.count_documents({"status": "PENDING_CONFIRMATION"})
    }

@app.get("/metrics")
def metrics():
    return METRICS

@app.get("/findings")
def list_findings(platform: str = "ALL"):
    q = {} if platform == "ALL" else {"platform": platform}
    return {"findings": list(findings_col.find(q, {"_id": 0}))}

@app.post("/scan/trigger")
def trigger_scan(payload: dict):
    target_platform = payload.get("platform") or "ALL"
    project_path = payload.get("project_path")
    force_rescan = bool(payload.get("force_rescan", False))
    scan_out = run_platform_vulnerability_scan(db, target_platform=target_platform, project_path=project_path, force_rescan=force_rescan)
    return {"platform": target_platform, "findings": scan_out["findings"], "telemetry": scan_out["telemetry"]}

@app.post("/mitigate/{finding_id}")
def mitigate_finding(finding_id: str):
    updated = apply_confirmed_mitigation(db, finding_id.upper())
    if not updated:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    return {"status": "mitigated", "finding": updated}

@app.get("/history/{session_id}")
def session_history(session_id: str):
    return {"session_id": session_id, "messages": get_history(session_id, n=25)}

@app.post("/chat")
def chat(request: dict):
    METRICS["chat_requests"] += 1
    session_id = request.get("session_id", "rayhaan-cti-session")
    user_msg = (request.get("message") or "").strip()
    platform_filter = request.get("platform", "ALL")
    lifecycle_filter = request.get("lifecycle", "ALL")
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    now = datetime.now(timezone.utc).isoformat()
    sessions_col.insert_one({
        "session_id": session_id,
        "role": "user",
        "content": user_msg,
        "platform": platform_filter,
        "lifecycle": lifecycle_filter,
        "timestamp": now
    })

    # Conversational Confirmation Check for Background Scanner Vulnerability Mitigation
    confirm_match = re.search(r"\b(?:confirm|mitigate|fix|approve)\s+(VULN-[A-Z]+-\d+)\b", user_msg, re.IGNORECASE)
    if confirm_match:
        fid = confirm_match.group(1).upper()
        updated = apply_confirmed_mitigation(db, fid)
        if updated:
            answer = (
                f"**Confirmed & Mitigated `{fid}` ({updated['title']})**\n"
                f"- **Platform:** {updated['platform']} | **CVE:** `{updated['cve']}`\n"
                f"- **Action Executed:** {updated['remediation_action']}\n"
                f"- **Threat State Updated:** `Active` -> **`Resolved`** (persisted to MongoDB `scan_findings` & `knowledge`)."
            )
            sessions_col.insert_one({
                "session_id": session_id, "role": "assistant", "content": answer,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return {"answer": answer, "sources": [], "engine": "remediation-executor", "mitigated": updated}

    chunks = retrieve_context(user_msg, platform_filter=platform_filter, lifecycle_filter=lifecycle_filter, n_results=3)
    history = get_history(session_id, n=5)
    answer, engine_used = generate_llm_response(user_msg, platform_filter, lifecycle_filter, chunks, history)
    METRICS["llm_mode_used"] = engine_used

    sessions_col.insert_one({
        "session_id": session_id,
        "role": "assistant",
        "content": answer,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    clean_sources = [{k: v for k, v in c.items() if k != "embedding"} for c in chunks]
    return {"answer": answer, "sources": clean_sources, "engine": engine_used}