"""Seed Cyber Threat Intelligence (CTI) data into MongoDB (lab_7 database)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.connection import get_db, reset_collection

THREAT_SOURCES = [
    {
        "source_id": "SRC-CTI-01",
        "name": "CTI Digest Feed",
        "url": "https://ctidigest.com/",
        "reliability": "A - Verified",
        "is_actual_threat_feed": True,
    },
    {
        "source_id": "SRC-AWESOME-01",
        "name": "Awesome Annual Security Reports",
        "url": "https://github.com/jacobdjwilson/awesome-annual-security-reports/",
        "reliability": "A - Verified",
        "is_actual_threat_feed": True,
    },
    {
        "source_id": "SRC-OSINT-02",
        "name": "Unverified Community Paste",
        "url": "https://osint.example.org/pastes",
        "reliability": "D - Unverified",
        "is_actual_threat_feed": False,
    },
]

THREAT_REPORTS = [
    {
        "report_id": "CTI-2026-001",
        "title": "Check Point Cybersecurity Report 2026: AI-Assisted Phishing & Ransomware",
        "vendor": "Check Point",
        "year": 2026,
        "category": "Ransomware",
        "severity": "Critical",
        "is_actual_threat": True,
        "source_id": "SRC-AWESOME-01",
        "summary": "Analyzes global ransomware campaigns, cloud perimeter exposures, and AI-generated phishing lures.",
        "tags": ["ransomware", "phishing", "ai-threats", "cloud"],
        "iocs": [
            {"type": "domain", "value": "login-update-verify.example", "confidence": 92},
            {"type": "sha256", "value": "e3b0c44298fc1c149afbf4c8996fb924", "confidence": 95},
        ],
    },
    {
        "report_id": "CTI-2026-002",
        "title": "Google Cybersecurity Forecast 2026: Zero-Day Exploitation & Cloud Identity",
        "vendor": "Google Cloud / GTIG",
        "year": 2026,
        "category": "Cloud Security",
        "severity": "High",
        "is_actual_threat": True,
        "source_id": "SRC-AWESOME-01",
        "summary": "Highlights state-sponsored actors using LLMs for reconnaissance and targeting cloud identity tokens.",
        "tags": ["cloud", "identity", "zero-day", "llm-malware"],
        "iocs": [
            {"type": "ip", "value": "198.51.100.42", "confidence": 88},
        ],
    },
    {
        "report_id": "CTI-2026-003",
        "title": "WithSecure Supply Chain Threat Report: Transitive Dependency Intrusions",
        "vendor": "WithSecure",
        "year": 2025,
        "category": "Supply Chain",
        "severity": "High",
        "is_actual_threat": True,
        "source_id": "SRC-CTI-01",
        "summary": "Upstream and downstream vendor dependency intrusions surged by 38% across open-source ecosystems.",
        "tags": ["supply-chain", "open-source", "ci-cd"],
        "iocs": [
            {"type": "package", "value": "malicious-helper-pkg@1.0.4", "confidence": 90},
        ],
    },
    {
        "report_id": "CTI-2026-004",
        "title": "Seqrite India Cyber Threat Report 2026: Endpoint Trojans & Healthcare Targeting",
        "vendor": "Seqrite",
        "year": 2026,
        "category": "Malware",
        "severity": "High",
        "is_actual_threat": True,
        "source_id": "SRC-AWESOME-01",
        "summary": "Telemetry from 8M+ endpoints shows Trojans constitute nearly 70% of malicious detections, hitting healthcare and education.",
        "tags": ["trojans", "endpoints", "healthcare", "ransomware"],
        "iocs": [
            {"type": "sha256", "value": "9f86d081884c7d659a2feaa0c55ad015", "confidence": 94},
        ],
    },
    {
        "report_id": "CTI-2026-005",
        "title": "APWG Phishing Activity Trends Report 2026",
        "vendor": "APWG",
        "year": 2026,
        "category": "Phishing",
        "severity": "Medium",
        "is_actual_threat": True,
        "source_id": "SRC-CTI-01",
        "summary": "Tracks worldwide phishing attack volume and brand impersonation trends in Q1 2026.",
        "tags": ["phishing", "brand-impersonation", "email"],
        "iocs": [
            {"type": "url", "value": "https://secure-auth-check.example/login", "confidence": 85},
        ],
    },
    {
        "report_id": "CTI-2026-006",
        "title": "Unverified Port Scan Chatter on Public Paste",
        "vendor": "Community OSINT",
        "year": 2026,
        "category": "Reconnaissance",
        "severity": "Low",
        "is_actual_threat": False,
        "source_id": "SRC-OSINT-02",
        "summary": "Routine automated scanner noise reported on public paste; classified as non-actionable false positive.",
        "tags": ["scanner", "noise", "false-positive"],
        "iocs": [],
    },
]


def seed_all():
    sources_col = reset_collection("lab_7", "threat_sources")
    reports_col = reset_collection("lab_7", "threat_reports")
    sources_col.insert_many(THREAT_SOURCES)
    reports_col.insert_many(THREAT_REPORTS)
    print(f"[OK] Seeded {len(THREAT_SOURCES)} threat sources and {len(THREAT_REPORTS)} threat reports into lab_7.")


if __name__ == "__main__":
    seed_all()
