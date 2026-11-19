import os
import time
import hashlib
import numpy as np
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def get_mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://host.docker.internal:27017/")

def get_client(retries: int = 20, delay: float = 2.0):
    uri = get_mongo_uri()
    last_err = None
    for _ in range(retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            return client
        except PyMongoError as exc:
            last_err = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to MongoDB at {uri}: {last_err}")

def get_db(client=None, db_name: str = None):
    if client is None:
        client = get_client()
    return client[db_name or os.getenv("DB_NAME", "rag_demo")]

def embed_texts(texts, dim: int = 384):
    """Generates normalized embeddings; uses Voyage AI if VOYAGE_API_KEY is set, else deterministic semantic vectors."""
    api_key = os.getenv("VOYAGE_API_KEY", "").strip()
    if api_key:
        try:
            from voyageai import Client as VoyageClient
            vc = VoyageClient(api_key=api_key)
            res = vc.embed(list(texts), model="voyage-3")
            return [np.array(e, dtype=np.float32) for e in res.embeddings]
        except Exception:
            pass

    vectors = []
    for text in texts:
        vec = np.zeros(dim, dtype=np.float32)
        tokens = [t.strip(".,!?;:\"'()[]").lower() for t in str(text).split() if t.strip()]
        if not tokens:
            tokens = ["empty"]
        for idx, tok in enumerate(tokens):
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            slot = int.from_bytes(h[:4], "little") % dim
            sign = 1.0 if (h[4] % 2 == 0) else -1.0
            weight = 1.0 + (1.0 / (1.0 + (idx % 7)))
            vec[slot] += sign * weight
            # Bigram context coupling for phrase similarity
            if idx + 1 < len(tokens):
                bh = hashlib.sha256(f"{tok}_{tokens[idx+1]}".encode("utf-8")).digest()
                bslot = int.from_bytes(bh[:4], "little") % dim
                vec[bslot] += 0.5 * (1.0 if (bh[4] % 2 == 0) else -1.0)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0
        vectors.append(vec)
    return vectors

def cosine_similarity(a, b) -> float:
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0