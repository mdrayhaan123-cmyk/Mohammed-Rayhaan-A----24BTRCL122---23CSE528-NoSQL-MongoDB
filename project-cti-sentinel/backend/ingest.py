import hashlib
import math
import os
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "llm_chat_app")

CTI_PLAYBOOKS = [
    {
        "doc_id": "CTI-WIN-001",
        "title": "Windows Print Spooler & SMBv1 Lateral Movement (CVE-2024-38063 / MS17-010)",
        "platform": "Windows",
        "lifecycle": "Active",
        "severity": "Critical",
        "cve": "CVE-2024-38063",
        "text": "Active exploitation detected on Windows 10/11 and Server hosts exposing SMBv1 and unpatched IPv6 TCP/IP stacks. Mitigation Procedure: 1) Disable SMBv1 via PowerShell 'Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart'. 2) Apply KB5041585 security cumulative update. 3) Block inbound TCP/445 and ICMPv6 Router Advertisements on untrusted interfaces.",
        "remediation_cmd": "Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart; Set-NetFirewallRule -DisplayGroup 'File and Printer Sharing' -Enabled False"
    },
    {
        "doc_id": "CTI-WIN-002",
        "title": "Windows PowerShell Constrained Language & Defender Tamper Bypass",
        "platform": "Windows",
        "lifecycle": "Evolving",
        "severity": "High",
        "cve": "CVE-2025-21298",
        "text": "Evolving infostealer campaign abuses unrestricted PowerShell execution policies and OLE memory corruption in Windows hosts. Mitigation Procedure: 1) Enforce RemoteSigned execution policy ('Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force'). 2) Enable Defender Tamper Protection and Attack Surface Reduction (ASR) rules blocking Office child processes.",
        "remediation_cmd": "Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force; Set-MpPreference -DisableRealtimeMonitoring $false"
    },
    {
        "doc_id": "CTI-LIN-001",
        "title": "Linux OpenSSH regreSSHion RCE & World-Writable /etc/cron.d Persistence",
        "platform": "Linux",
        "lifecycle": "Active",
        "severity": "Critical",
        "cve": "CVE-2024-6387",
        "text": "Active unauthenticated remote code execution race condition in glibc-based Linux OpenSSH servers (8.5p1 to 9.7p1) alongside weak SSH root login settings. Mitigation Procedure: 1) Upgrade openssh-server to >= 9.8p1. 2) Set 'PermitRootLogin no' and 'LoginGraceTime 0' in /etc/ssh/sshd_config. 3) Reload sshd service and audit /etc/cron.d permissions.",
        "remediation_cmd": "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config && systemctl reload sshd"
    },
    {
        "doc_id": "CTI-LIN-002",
        "title": "Linux Kernel io_uring Privilege Escalation & Container Escape",
        "platform": "Linux",
        "lifecycle": "Anticipated",
        "severity": "High",
        "cve": "CVE-2025-21756",
        "text": "Anticipated exploitation wave targeting containerized workloads on Linux kernels < 6.8 where unprivileged io_uring syscalls are enabled. Mitigation Procedure: 1) Set sysctl 'kernel.io_uring_disabled=2'. 2) Drop CAP_SYS_ADMIN in Docker/Kubernetes securityContext and apply default seccomp profiles.",
        "remediation_cmd": "sysctl -w kernel.io_uring_disabled=2"
    },
    {
        "doc_id": "CTI-MAC-001",
        "title": "macOS Gatekeeper & TCC Transparency Bypass via Unsigned DMG Archives",
        "platform": "macOS",
        "lifecycle": "Evolving",
        "severity": "High",
        "cve": "CVE-2024-44243",
        "text": "Evolving macOS stealer malware (Atomic/Poseidon variants) tricks users into running xattr quarantine-stripped binaries to harvest Keychain and browser tokens. Mitigation Procedure: 1) Verify Gatekeeper is enforced via 'sudo spctl --master-enable'. 2) Restrict System Integrity Protection (SIP) and audit ~/Library/LaunchAgents.",
        "remediation_cmd": "sudo spctl --master-enable && defaults write com.apple.LaunchServices LSQuarantine -bool true"
    },
    {
        "doc_id": "CTI-AND-001",
        "title": "Android Accessibility Service Overlay & Malicious APK Sideloading",
        "platform": "Android",
        "lifecycle": "Active",
        "severity": "Critical",
        "cve": "CVE-2024-43093",
        "text": "Active banking trojans exploit Android Accessibility permissions and external storage privilege escalation on unpatched Android 12-14 devices. Mitigation Procedure: 1) Disable 'Install unknown apps' across browsers/messengers. 2) Enforce Google Play Protect scanning. 3) Revoke Accessibility permissions for non-system packages.",
        "remediation_cmd": "adb shell settings put secure install_non_market_apps 0"
    },
    {
        "doc_id": "CTI-IOS-001",
        "title": "iOS WebKit Zero-Click Memory Corruption & Spyware Lockdown Defense",
        "platform": "iOS",
        "lifecycle": "Anticipated",
        "severity": "Critical",
        "cve": "CVE-2025-24085",
        "text": "Anticipated mercenary spyware chains target WebKit JIT compilation and iMessage attachment parsers on iOS < 18.3. Mitigation Procedure: 1) Update immediately to iOS 18.3+. 2) Enable Lockdown Mode under Settings > Privacy & Security for high-risk executives to disable JIT JavaScript and block unknown FaceTime/attachment vectors.",
        "remediation_cmd": "mdm-push --profile enable-lockdown-mode --os-update-enforce 18.3"
    },
    {
        "doc_id": "CTI-RES-001",
        "title": "Resolved: MongoDB Unauthenticated 27017 Exposure & SCRAM-SHA-256 Hardening",
        "platform": "Linux",
        "lifecycle": "Resolved",
        "severity": "Medium",
        "cve": "CVE-2024-7553",
        "text": "Resolved incident pattern where legacy MongoDB instances bound to 0.0.0.0 without --auth enabled. Post-Incident Verification: Confirmed --auth with SCRAM-SHA-256, TLS 1.3 transport encryption, and least-privilege RBAC roles enforced across replica set rs0.",
        "remediation_cmd": "mongosh --eval 'db.adminCommand({getParameter: 1, authenticationMechanisms: 1})'"
    }
]

def embed_text(text: str, dims: int = 384) -> list[float]:
    """Deterministic 384-d L2-normalized semantic token hash embedding (works 100% offline)."""
    vec = [0.0] * dims
    tokens = [t.strip(".,:;()[]{}'\"/\\-").lower() for t in text.split() if len(t) > 1]
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, 32, 2):
            idx = ((h[i] << 8) | h[i + 1]) % dims
            sign = 1.0 if (h[i] % 2 == 0) else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]

def seed_knowledge_base(db=None):
    if db is None:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
    kb = db["knowledge"]
    kb.create_index([("platform", ASCENDING), ("lifecycle", ASCENDING)])
    kb.create_index([("doc_id", ASCENDING)], unique=True)

    inserted = 0
    for item in CTI_PLAYBOOKS:
        doc = {
            **item,
            "chunk_index": 0,
            "embedding": embed_text(f"{item['platform']} {item['lifecycle']} {item['title']} {item['text']}"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        res = kb.update_one({"doc_id": item["doc_id"]}, {"$set": doc}, upsert=True)
        if res.upserted_id:
            inserted += 1
    return {"total_playbooks": kb.count_documents({}), "newly_inserted": inserted}

if __name__ == "__main__":
    print(seed_knowledge_base())