import os
from datetime import datetime, timezone
from tabulate import tabulate
from pymongo.errors import OperationFailure
from connection import get_client, get_db, embed_texts, cosine_similarity

CTI_DOCUMENTS = [
    {
        "source": "cti_apt_ransomware_brief.md",
        "text": (
            "Cyber threat intelligence analysts track coordinated ransomware campaigns targeting enterprise "
            "identity providers and exposed remote management interfaces. Adversaries conduct initial "
            "reconnaissance, harvest valid session tokens, escalate privileges across active directory "
            "domains, and exfiltrate sensitive telemetry before deploying encryption payloads. Early detection "
            "relies on correlating anomalous authentication spikes, lateral SMB or WinRM movement, and "
            "unexpected shadow copy deletion commands across endpoint detection and response sensors."
        ),
    },
    {
        "source": "cti_phishing_c2_infrastructure.md",
        "text": (
            "Modern spear-phishing operations pair lookalike domains and adversary-in-the-middle reverse "
            "proxies to bypass multi-factor authentication prompts. Once initial access is established, "
            "malicious implants beacon outbound over HTTPS or DNS tunneling to command-and-control nodes "
            "hosted on rotating cloud infrastructure. Threat hunting teams enrich suspicious IP addresses, "
            "TLS certificate fingerprints, and ASN reputation scores to block active C2 channels and isolate "
            "compromised workstations before credential harvesting spreads across cloud workloads."
        ),
    },
    {
        "source": "cti_vulnerability_zero_day_triage.md",
        "text": (
            "Prioritizing software vulnerabilities requires combining exploitability telemetry, active "
            "in-the-wild exploitation feeds, and asset criticality rather than relying solely on base "
            "severity scores. Edge appliances, VPN gateways, and unpatched serialization endpoints face "
            "rapid automated scanning within hours of public disclosure. Security operations teams apply "
            "virtual WAF rules, rotate exposed secrets, and schedule emergency patching for internet-facing "
            "services with known exploit weaponization."
        ),
    },
    {
        "source": "cti_supply_chain_ioc_sharing.md",
        "text": (
            "Software supply chain defense focuses on verifying build provenance, signing artifacts, and "
            "monitoring third-party package registries for typosquatting or compromised maintainer tokens. "
            "Structured threat intelligence feeds using STIX and TAXII allow security platforms to share "
            "indicators of compromise such as file hashes, domain names, and TTP mappings across teams. "
            "Automated playbook orchestration enriches alerts with historical incident context to reduce "
            "mean time to detect and respond."
        ),
    },
]

def chunk_into_words(text: str, chunk_size: int = 100, overlap: int = 15):
    words = text.split()
    if len(words) <= chunk_size:
        return [" ".join(words)]
    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        part = words[start:start + chunk_size]
        if len(part) < 20 and chunks:
            chunks[-1] = chunks[-1] + " " + " ".join(part)
            break
        chunks.append(" ".join(part))
        if start + chunk_size >= len(words):
            break
    return chunks

def retrieve_top_chunks(collection, query: str, limit: int = 3, num_candidates: int = 20):
    q_vec = embed_texts([query])[0].tolist()
    index_name = os.getenv("VECTOR_INDEX_NAME", "vector_index")

    # Attempt Atlas $vectorSearch when available; fall back cleanly to cosine similarity over stored embeddings
    pipeline = [
        {
            "$vectorSearch": {
                "index": index_name,
                "path": "embedding",
                "queryVector": q_vec,
                "numCandidates": num_candidates,
                "limit": limit,
            }
        },
        {"$project": {"text": 1, "source": 1, "chunk_id": 1, "score": {"$meta": "vectorSearchScore"}, "_id": 0}},
    ]
    try:
        hits = list(collection.aggregate(pipeline))
        if hits:
            return hits
    except OperationFailure:
        pass

    scored = []
    for doc in collection.find({}, {"_id": 0, "text": 1, "source": 1, "chunk_id": 1, "embedding": 1}):
        score = cosine_similarity(q_vec, doc.get("embedding", []))
        scored.append({
            "text": doc["text"],
            "source": doc["source"],
            "chunk_id": doc.get("chunk_id", 0),
            "score": round(score, 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]

def get_recent_conversation(conv_coll, user_id: str, max_messages: int = 5):
    msgs = list(
        conv_coll.find({"user_id": user_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(max_messages)
    )
    msgs.reverse()
    return msgs

def generate_rag_response(db, user_id: str, query: str, top_chunks: list) -> str:
    history = get_recent_conversation(db.conversations, user_id=user_id, max_messages=5)
    context_snippets = "\n".join(
        f"[{i+1}] ({c['source']}, score={c['score']:.4f}): {c['text'][:180]}..."
        for i, c in enumerate(top_chunks)
    )
    history_text = " | ".join(f"{m['role']}: {m['content'][:80]}" for m in history) if history else "None"

    # Grounded synthesis prompt constructed from retrieved chunks + last 5 conversation turns
    _prompt = (
        f"System Context History (last {len(history)} msgs): {history_text}\n"
        f"Retrieved Threat Intelligence Chunks:\n{context_snippets}\n"
        f"Question: {query}"
    )
    primary_source = top_chunks[0]["source"] if top_chunks else "cti_knowledge_base"
    key_point = top_chunks[0]["text"][:210].rstrip() if top_chunks else "No matching chunks found."
    answer = (
        f"Based on '{primary_source}' (and {len(history)} prior context message(s) for {user_id}): "
        f"{key_point}... Recommended action: correlate endpoint/network telemetry and apply targeted mitigations."
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    db.conversations.insert_many([
        {"user_id": user_id, "timestamp": now_iso, "role": "user", "content": query},
        {"user_id": user_id, "timestamp": now_iso, "role": "assistant", "content": answer},
    ])
    return answer

def main():
    print("=" * 78)
    print("LAB 17.1 & Activity 17.1: Threat Intelligence RAG & Conversation Memory")
    print("=" * 78)

    client = get_client()
    db = get_db(client)
    docs_coll = db["documents"]
    docs_coll.drop()
    db.conversations.drop()

    chunk_records = []
    raw_texts = []
    for doc in CTI_DOCUMENTS:
        pieces = chunk_into_words(doc["text"], chunk_size=100, overlap=15)
        for idx, piece in enumerate(pieces):
            chunk_records.append({
                "text": piece,
                "source": doc["source"],
                "chunk_id": idx,
                "word_count": len(piece.split()),
            })
            raw_texts.append(piece)

    vectors = embed_texts(raw_texts, dim=384)
    for rec, vec in zip(chunk_records, vectors):
        rec["embedding"] = vec.tolist()

    docs_coll.insert_many(chunk_records)
    print(f"[INGEST] Chunked {len(CTI_DOCUMENTS)} CTI documents into {len(chunk_records)} ~100-word segments & stored 384-d embeddings in '{db.name}.documents'")

    turns = [
        ("analyst_rayhaan", "How do attackers move laterally and evade MFA during ransomware or phishing intrusions?"),
        ("analyst_rayhaan", "Which vulnerability triage and IOC sharing steps should we prioritize next?"),
    ]
    for turn_num, (uid, q) in enumerate(turns, start=1):
        top3 = retrieve_top_chunks(docs_coll, q, limit=3, num_candidates=20)
        ans = generate_rag_response(db, uid, q, top3)
        rows = [[i + 1, c["source"], round(c["score"], 4), c["text"][:68] + "..."] for i, c in enumerate(top3)]
        print(f"\n[RAG TURN {turn_num}] Query: {q}")
        print(tabulate(rows, headers=["Rank", "Source", "Score", "Retrieved Chunk"], tablefmt="grid"))
        print(f"  [ASSISTANT] {ans}")

    stored_msgs = db.conversations.count_documents({"user_id": "analyst_rayhaan"})
    print(f"\n[MEMORY] Stored {stored_msgs} multi-turn messages in '{db.name}.conversations' (last 5 included per turn)")

if __name__ == "__main__":
    main()