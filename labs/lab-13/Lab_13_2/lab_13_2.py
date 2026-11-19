import os
import yaml
from connection import get_db

def main():
    print("=" * 76)
    print("LAB 13.2: Kubernetes StatefulSet Manifest Validation & Orchestration Report")
    print("=" * 76)

    svc_path = os.path.join(os.path.dirname(__file__), "..", "k8s", "mongo-headless-svc.yaml")
    sts_path = os.path.join(os.path.dirname(__file__), "..", "k8s", "mongo-statefulset.yaml")

    with open(svc_path, "r", encoding="utf-8") as f:
        svc = yaml.safe_load(f)
    with open(sts_path, "r", encoding="utf-8") as f:
        sts = yaml.safe_load(f)

    replicas = sts["spec"]["replicas"]
    svc_name = sts["spec"]["serviceName"]
    cluster_ip = svc["spec"]["clusterIP"]
    init_name = sts["spec"]["template"]["spec"]["initContainers"][0]["name"]
    pvc_storage = sts["spec"]["volumeClaimTemplates"][0]["spec"]["resources"]["requests"]["storage"]

    print("[KUBERNETES MANIFESTS VERIFIED]")
    print(f"  1. Headless Service : {svc['metadata']['name']} (clusterIP={cluster_ip})")
    print(f"  2. StatefulSet      : {sts['metadata']['name']} (replicas={replicas}, serviceName={svc_name})")
    print(f"  3. InitContainer    : {init_name} -> generates /etc/mongodb/keyfile (chmod 400)")
    print(f"  4. Storage Template : volumeClaimTemplates ({pvc_storage} ReadWriteOnce per pod)")
    print("  5. Stable DNS FQDN  : mongo-{0,1,2}.mongo-headless-svc:27017")

    # Store orchestration comparison in lab_13 for Compass inspection
    db = get_db()
    db.k8s_manifests.drop()
    db.k8s_manifests.insert_many([
        {
            "platform": "Docker Compose",
            "self_healing": "Basic restart policies (restart: unless-stopped); manual host recovery",
            "network_identity": "Static container service names (mongo1, mongo2, mongo3)",
            "storage": "Named Docker volumes bound to single host",
            "operational_complexity": "Low (single YAML file, ideal for single-host dev/staging)",
        },
        {
            "platform": "Kubernetes StatefulSet",
            "self_healing": "Automatic pod recreation & rescheduling on node failure (kubectl delete pod mongo-2)",
            "network_identity": "Ordinal headless DNS (mongo-0.mongo-headless-svc) preserved across restarts",
            "storage": "Dynamic PersistentVolumeClaims reattached automatically to recreated pods",
            "operational_complexity": "High (requires cluster control plane, StorageClass, probes, headless Service)",
        },
    ])
    print(f"\n[SEED] Saved Docker Compose vs. Kubernetes comparison into '{db.name}.k8s_manifests'")

    print("\n--- Operational Comparison: Docker Compose vs. Kubernetes StatefulSet ---")
    print("  Feature          | Docker Compose                  | Kubernetes StatefulSet")
    print("  -----------------+---------------------------------+-----------------------------------------")
    print("  Self-Healing     | Container restart on single host| Auto pod recreation + node rescheduling")
    print("  Network Identity | Container DNS (mongo1..3)       | Ordinal DNS (mongo-0.mongo-headless-svc)")
    print("  Storage          | Local named volumes             | PersistentVolumeClaims (auto-reattach)")
    print("  Complexity       | Low (single compose YAML)       | High (StatefulSet + Headless Svc + PVC)")

if __name__ == "__main__":
    main()