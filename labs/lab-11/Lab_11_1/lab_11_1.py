def main():
    print("=" * 76)
    print("LAB 11.1: E-Commerce Order Management Shard Key Evaluation")
    print("=" * 76)

    candidates = [
        {
            "key": "order_id",
            "cardinality": "High (Unique UUID/ID)",
            "distribution": "Even (UUID) / Hotspot (Sequential)",
            "targeting": "Poor (customer_id queries broadcast)",
            "score": "2/5 - Rejected",
        },
        {
            "key": "customer_id",
            "cardinality": "High (Per Customer)",
            "distribution": "Skewed (Heavy buyers create jumbo chunks)",
            "targeting": "Excellent (Single-shard customer queries)",
            "score": "3.5/5 - Skew Risk",
        },
        {
            "key": "order_date",
            "cardinality": "Low-Medium (Time buckets)",
            "distribution": "Severe Hotspot (Monotonic MaxKey chunk)",
            "targeting": "Good for date ranges only",
            "score": "1.5/5 - Rejected",
        },
        {
            "key": "{ customer_id: 'hashed' }",
            "cardinality": "High (MD5 hash space)",
            "distribution": "Even (Randomized across all shards)",
            "targeting": "Good (Targeted equality on customer_id)",
            "score": "4.8/5 - RECOMMENDED",
        },
    ]

    header = f"{'Candidate Key':<26} | {'Cardinality':<24} | {'Distribution':<39} | {'Verdict'}"
    print(header)
    print("-" * len(header))
    for c in candidates:
        print(f"{c['key']:<26} | {c['cardinality']:<24} | {c['distribution']:<39} | {c['score']}")

    print("\n[RECOMMENDATION] { customer_id: 'hashed' }")
    print("  - Eliminates write hotspots and heavy-buyer data skew via MD5 hash distribution.")
    print("  - Routes equality queries by customer_id directly to a single owning shard.")

if __name__ == "__main__":
    main()