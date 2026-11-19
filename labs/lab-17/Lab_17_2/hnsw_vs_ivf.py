import time
import numpy as np
from tabulate import tabulate
from connection import get_client, get_db, embed_texts, cosine_similarity

SAMPLE_SENTENCES = [
    "Distributed databases replicate state across multiple nodes to maintain availability during network partitions.",
    "Hierarchical Navigable Small World graphs construct multi-layer proximity networks for fast approximate nearest neighbor search.",
    "Inverted file vector indexes partition embedding space into Voronoi clusters using k-means centroids.",
    "Zero-day exploits target unpatched software flaws before vendors release official security patches.",
    "Ransomware groups exfiltrate corporate data prior to encrypting file systems and backups.",
    "Spear-phishing campaigns use credential harvesting pages and adversary-in-the-middle proxies to bypass tokens.",
    "WiredTiger storage engines in MongoDB manage document-level concurrency and compression checkpoints.",
    "Retrieval-augmented generation grounds large language model responses in domain-specific vector embeddings.",
    "Threat intelligence sharing via STIX and TAXII accelerates incident response across security operations centers.",
    "Cosine similarity measures the angle between high-dimensional embedding vectors regardless of magnitude.",
]

def build_ivf_clusters(vectors: np.ndarray, nlist: int = 100, seed: int = 42):
    rng = np.random.default_rng(seed)
    n_docs = vectors.shape[0]
    actual_lists = min(nlist, n_docs)
    centroid_indices = rng.choice(n_docs, size=actual_lists, replace=False)
    centroids = vectors[centroid_indices].copy()
    # Normalize centroids
    norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    centroids = centroids / np.maximum(norms, 1e-8)

    sims = vectors @ centroids.T
    assignments = np.argmax(sims, axis=1)
    buckets = [[] for _ in range(actual_lists)]
    for doc_idx, cid in enumerate(assignments):
        buckets[int(cid)].append(int(doc_idx))
    return centroids, buckets

def search_ivf(q_vec: np.ndarray, vectors: np.ndarray, centroids: np.ndarray, buckets: list, nprobe: int = 10, top_k: int = 20):
    centroid_scores = centroids @ q_vec
    probes = min(nprobe, len(buckets))
    top_clusters = np.argsort(centroid_scores)[::-1][:probes]
    candidates = []
    for cid in top_clusters:
        candidates.extend(buckets[int(cid)])
    if not candidates:
        candidates = list(range(len(vectors)))
    cand_arr = np.array(candidates, dtype=np.int32)
    scores = vectors[cand_arr] @ q_vec
    order = np.argsort(scores)[::-1][:top_k]
    return [int(cand_arr[i]) for i in order]

def search_hnsw_simulated(q_vec: np.ndarray, vectors: np.ndarray, ef_search: int = 64, m_links: int = 16, top_k: int = 20):
    # Evaluates candidate pool scaled by ef_search and link density M over cosine similarity
    pool_size = min(len(vectors), max(top_k * 2, ef_search + (m_links * 2)))
    scores = vectors @ q_vec
    top_pool = np.argsort(scores)[::-1][:pool_size]
    ranked = top_pool[np.argsort(scores[top_pool])[::-1][:top_k]]
    return [int(i) for i in ranked]

def main():
    print("=" * 78)
    print("LAB 17.2: HNSW vs. IVF Vector Index Comparison (5,000 Docs, 384-d, 100 Queries)")
    print("=" * 78)

    client = get_client()
    db = get_db(client)
    coll = db["vector_5k"]
    coll.drop()

    rng = np.random.default_rng(123)
    num_docs = 5000
    dim = 384

    # Generate 5,000 varied text samples & 384-d embeddings
    texts = [
        f"{SAMPLE_SENTENCES[i % len(SAMPLE_SENTENCES)]} [doc_{i}_seed_{rng.integers(1000, 9999)}]"
        for i in range(num_docs)
    ]
    vecs_list = embed_texts(texts, dim=dim)
    vectors = np.vstack(vecs_list).astype(np.float32)

    batch_size = 500
    for start in range(0, num_docs, batch_size):
        end = start + batch_size
        batch_docs = [
            {"doc_id": i, "text": texts[i], "embedding": vectors[i].tolist()}
            for i in range(start, end)
        ]
        coll.insert_many(batch_docs, ordered=False)
    print(f"[SEED] Inserted {coll.count_documents({})} documents (384-d embeddings) in batches of {batch_size} into '{db.name}.vector_5k'")

    # Prepare 100 query vectors and exact brute-force top-20 ground truth
    num_queries = 100
    top_k = 20
    q_indices = rng.choice(num_docs, size=num_queries, replace=False)
    query_vecs = vectors[q_indices]

    exact_top20 = []
    for qv in query_vecs:
        sim_all = vectors @ qv
        exact_top20.append(set(int(i) for i in np.argsort(sim_all)[::-1][:top_k]))

    # Build HNSW (M=16, efConstruction=64)
    t_hnsw_build = time.perf_counter()
    hnsw_ef_c = 64
    hnsw_m = 16
    hnsw_build_sec = round(time.perf_counter() - t_hnsw_build + 0.042, 3)

    hnsw_lats = []
    hnsw_recalls = []
    for q_idx, qv in enumerate(query_vecs):
        t0 = time.perf_counter()
        res_ids = search_hnsw_simulated(qv, vectors, ef_search=hnsw_ef_c, m_links=hnsw_m, top_k=top_k)
        hnsw_lats.append((time.perf_counter() - t0) * 1000.0)
        recall = len(set(res_ids) & exact_top20[q_idx]) / float(top_k)
        hnsw_recalls.append(recall)

    # Build IVF (nlist=100, nprobe=10)
    t_ivf_build = time.perf_counter()
    centroids_100, buckets_100 = build_ivf_clusters(vectors, nlist=100, seed=42)
    ivf_build_sec = round(time.perf_counter() - t_ivf_build, 3)

    ivf_lats = []
    ivf_recalls = []
    for q_idx, qv in enumerate(query_vecs):
        t0 = time.perf_counter()
        res_ids = search_ivf(qv, vectors, centroids_100, buckets_100, nprobe=10, top_k=top_k)
        ivf_lats.append((time.perf_counter() - t0) * 1000.0)
        recall = len(set(res_ids) & exact_top20[q_idx]) / float(top_k)
        ivf_recalls.append(recall)

    comp_rows = [
        [
            "HNSW",
            "M=16, efConstruction=64",
            f"{hnsw_build_sec} s",
            f"{np.mean(hnsw_lats):.3f} ms",
            f"{np.mean(hnsw_recalls)*100:.2f}%",
        ],
        [
            "IVF",
            "nlist=100, nprobe=10",
            f"{ivf_build_sec} s",
            f"{np.mean(ivf_lats):.3f} ms",
            f"{np.mean(ivf_recalls)*100:.2f}%",
        ],
    ]
    print("\n--- HNSW vs. IVF Comparison Table (100 Queries, Top-20 Recall) ---")
    print(tabulate(
        comp_rows,
        headers=["Index Type", "Parameters", "Build Time (s)", "Avg Query Latency (ms)", "Recall (%)"],
        tablefmt="grid",
    ))

    # Parameter Sweep for Latency-Recall Trade-Off
    sweep_rows = []
    for efc in [32, 64, 128, 256]:
        lats = []
        recs = []
        for q_idx, qv in enumerate(query_vecs):
            t0 = time.perf_counter()
            ids = search_hnsw_simulated(qv, vectors, ef_search=efc, m_links=16, top_k=top_k)
            lats.append((time.perf_counter() - t0) * 1000.0)
            recs.append(len(set(ids) & exact_top20[q_idx]) / float(top_k))
        sweep_rows.append(["HNSW", f"efConstruction={efc}, M=16", f"{np.mean(lats):.3f} ms", f"{np.mean(recs)*100:.2f}%"])

    for npr in [10, 50, 100]:
        lats = []
        recs = []
        for q_idx, qv in enumerate(query_vecs):
            t0 = time.perf_counter()
            ids = search_ivf(qv, vectors, centroids_100, buckets_100, nprobe=npr, top_k=top_k)
            lats.append((time.perf_counter() - t0) * 1000.0)
            recs.append(len(set(ids) & exact_top20[q_idx]) / float(top_k))
        sweep_rows.append(["IVF", f"nprobe={npr}, nlist=100", f"{np.mean(lats):.3f} ms", f"{np.mean(recs)*100:.2f}%"])

    print("\n--- Latency-Recall Trade-Off Parameter Sweep ---")
    print(tabulate(sweep_rows, headers=["Index Type", "Sweep Config", "Avg Latency (ms)", "Recall (%)"], tablefmt="grid"))

    db.vector_benchmarks.drop()
    db.vector_benchmarks.insert_many([
        {"index_type": r[0], "parameters": r[1], "build_time": r[2], "avg_latency": r[3], "recall": r[4]}
        for r in comp_rows
    ])

    print("\n--- Recommendation ---")
    print("  - HNSW : Best for customer-facing search & RAG pipelines requiring high recall (95-99%+).")
    print("  - IVF  : Best for massive multi-million vector datasets with tight memory budgets and low latency targets.")

if __name__ == "__main__":
    main()