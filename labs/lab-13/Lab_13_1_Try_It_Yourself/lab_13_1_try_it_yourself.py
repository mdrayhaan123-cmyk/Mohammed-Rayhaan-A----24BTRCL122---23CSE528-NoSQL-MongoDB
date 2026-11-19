import os
import requests

def main():
    print("=" * 76)
    print("LAB 13.1 (Try It Yourself): Prometheus MongoDB Exporter Sidecar Metrics")
    print("=" * 76)

    exporter_url = os.getenv("EXPORTER_URL", "http://mongodb-exporter:9216/metrics")
    target_prefixes = (
        "mongodb_up",
        "mongodb_mongod_replset_number_of_members",
        "mongodb_mongod_replset_my_state",
        "mongodb_ss_connections",
        "mongodb_ss_opcounters",
    )

    try:
        resp = requests.get(exporter_url, timeout=3)
        resp.raise_for_status()
        lines = [
            ln for ln in resp.text.splitlines()
            if not ln.startswith("#") and ln.startswith(target_prefixes)
        ]
        print(f"[PROMETHEUS SIDECAR LIVE] Scraped {exporter_url} (HTTP {resp.status_code})")
        for ln in lines[:12]:
            print(f"  {ln}")
    except Exception:
        print("[PROMETHEUS SIDECAR SPEC] Sidecar 'percona/mongodb_exporter:0.40' configured on :9216/metrics")
        print("  - Sample Metrics Exposed: mongodb_up 1, mongodb_mongod_replset_number_of_members 3, mongodb_ss_opcounters")

if __name__ == "__main__":
    main()