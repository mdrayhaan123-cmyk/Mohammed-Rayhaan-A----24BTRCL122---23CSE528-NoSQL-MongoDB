import os
import time
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from tabulate import tabulate
from pymongo.errors import OperationFailure
from connection import get_client, get_db

class _MockWebhookHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        _MockWebhookHandler.received.append(json.loads(body))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):
        return

def start_local_webhook_receiver():
    server = HTTPServer(("127.0.0.1", 0), _MockWebhookHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, f"http://127.0.0.1:{port}/webhook"

def send_webhook_alert(webhook_url: str, alert_payload: dict) -> bool:
    if not webhook_url:
        return False
    try:
        resp = requests.post(webhook_url, json=alert_payload, timeout=4)
        resp.raise_for_status()
        print(f"  [WEBHOOK SENT] POST {webhook_url} -> HTTP {resp.status_code}")
        return True
    except Exception as exc:
        print(f"  [WEBHOOK ERROR] Failed to deliver alert to {webhook_url}: {exc}")
        return False

def collect_metrics(client):
    srv = client.admin.command("serverStatus")
    conns = srv.get("connections", {})
    ops = srv.get("opcounters", {})
    wt_cache = srv.get("wiredTiger", {}).get("cache", {})

    bytes_read_into = wt_cache.get("bytes read into cache", 0)
    bytes_in_cache = wt_cache.get("bytes currently in the cache", 1)
    max_cache = wt_cache.get("maximum bytes configured", 1)
    # Cache hit ratio approximation from WiredTiger read-into-cache vs cached footprint
    total_reads = bytes_in_cache + bytes_read_into
    cache_hit_ratio = (bytes_in_cache / total_reads) if total_reads > 0 else 1.0

    rep_lag_sec = 0.0
    rep_state = "STANDALONE"
    try:
        rs = client.admin.command("replSetGetStatus")
        rep_state = f"{rs.get('set')} ({len(rs.get('members', []))} nodes)"
        primary_optime = None
        max_lag = 0.0
        for m in rs.get("members", []):
            if m.get("stateStr") == "PRIMARY":
                primary_optime = m.get("optimeDate")
        if primary_optime:
            for m in rs.get("members", []):
                if m.get("stateStr") == "SECONDARY" and m.get("optimeDate"):
                    lag = abs((primary_optime - m["optimeDate"]).total_seconds())
                    max_lag = max(max_lag, lag)
        rep_lag_sec = round(max_lag, 3)
    except OperationFailure:
        pass

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections_current": conns.get("current", 0),
        "connections_available": conns.get("available", 0),
        "op_insert": ops.get("insert", 0),
        "op_query": ops.get("query", 0),
        "op_update": ops.get("update", 0),
        "op_delete": ops.get("delete", 0),
        "wt_cached_mb": round(bytes_in_cache / (1024 * 1024), 2),
        "wt_max_mb": round(max_cache / (1024 * 1024), 2),
        "cache_hit_ratio": round(cache_hit_ratio, 4),
        "replica_set": rep_state,
        "replication_lag_sec": rep_lag_sec,
    }

def evaluate_alerts(metrics: dict, webhook_url: str, force_test_breach: bool = False):
    alerts = []
    hit_ratio = 0.72 if force_test_breach else metrics["cache_hit_ratio"]
    rep_lag = 14.5 if force_test_breach else metrics["replication_lag_sec"]

    if hit_ratio < 0.80:
        alerts.append(f"WARNING: WiredTiger cache hit ratio dropped to {hit_ratio*100:.1f}% (< 80.0% threshold)")
    if rep_lag > 10.0:
        alerts.append(f"WARNING: Replication lag reached {rep_lag:.1f}s (> 10.0s threshold)")

    for msg in alerts:
        print(f"  {msg}")
        payload = {
            "text": msg,
            "service": "NoSQL-Lab14-Monitor",
            "timestamp": metrics["timestamp"],
            "metrics": {
                "cache_hit_ratio_pct": round(hit_ratio * 100, 2),
                "replication_lag_sec": rep_lag,
            },
        }
        send_webhook_alert(webhook_url, payload)
    return alerts

def main():
    print("=" * 78)
    print("LAB 14.1 & Activity 14.1: MongoDB Monitoring Dashboard & Webhook Alerting")
    print("=" * 78)

    client = get_client()
    db = get_db(client)
    log_path = os.getenv("METRICS_LOG_PATH", "/app/logs/metrics.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # Support either user-supplied Slack/Discord WEBHOOK_URL or local verification receiver
    user_webhook = os.getenv("WEBHOOK_URL", "").strip()
    local_srv = None
    if not user_webhook:
        local_srv, webhook_url = start_local_webhook_receiver()
    else:
        webhook_url = user_webhook

    sample_count = int(os.getenv("MONITOR_SAMPLES", "2"))
    interval_sec = float(os.getenv("MONITOR_INTERVAL_SEC", "2"))

    for idx in range(1, sample_count + 1):
        m = collect_metrics(client)
        table_rows = [
            ["Timestamp (UTC)", m["timestamp"]],
            ["Topology", m["replica_set"]],
            ["Connections (Current / Avail)", f"{m['connections_current']} / {m['connections_available']}"],
            ["Opcounters (ins/qry/upd/del)", f"{m['op_insert']} / {m['op_query']} / {m['op_update']} / {m['op_delete']}"],
            ["WiredTiger Cache (Used / Max)", f"{m['wt_cached_mb']} MB / {m['wt_max_mb']} MB"],
            ["Cache Hit Ratio", f"{m['cache_hit_ratio']*100:.2f}%"],
            ["Replication Lag", f"{m['replication_lag_sec']} s"],
        ]
        rendered = tabulate(table_rows, headers=["Metric", "Value"], tablefmt="grid")
        print(f"\n[SAMPLE {idx}/{sample_count}]")
        print(rendered)

        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n--- Snapshot {idx} ({m['timestamp']}) ---\n{rendered}\n")

        # Persist monitoring snapshot into lab_14.monitoring_logs for Compass inspection
        db.monitoring_logs.insert_one(dict(m))

        if idx == sample_count:
            print("\n--- Threshold Alert & Webhook Verification (Simulating <80% Hit Ratio & >10s Lag) ---")
            evaluate_alerts(m, webhook_url, force_test_breach=True)
        else:
            evaluate_alerts(m, webhook_url, force_test_breach=False)
            time.sleep(interval_sec)

    if local_srv:
        print(f"  [WEBHOOK VERIFIED] Local receiver captured {len(_MockWebhookHandler.received)} alert payload(s)")
        local_srv.shutdown()

    print(f"[LOG SAVED] Appended formatted telemetry snapshots to '{log_path}'")

if __name__ == "__main__":
    main()