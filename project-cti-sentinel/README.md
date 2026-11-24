# CTI Sentinel - LLM-Backed Threat Intelligence & Vulnerability Remediation Platform (23CSE528)

**Student:** Mohammed Rayhaan A (24BTRCL122)
**Course:** 23CSE528 - NoSQL Databases using MongoDB (Synthesis of Exercises 1-18)

## Features
- MongoDB Vector RAG (knowledge collection) across Windows, Linux, macOS, Android, and iOS
- Threat Lifecycle Classification: Anticipated, Active, Evolving, and Resolved threats
- Persistent Multi-Turn Conversation Memory (sessions collection)
- Background Vulnerability Scanner Daemon (scanner_daemon.py) with user-confirmed chat mitigation
- Full Docker Compose Stack (mongo:7, FastAPI :8000, Streamlit :8501)

## Demo & Evaluation Prompts

### 1. Live Threat Scan & Host Security Telemetry
- "Run a live security scan on my system right now and tell me if any ports, firewall rules, or Defender settings need attention."
- "Check my Windows host for active threats, exposed `.env` or key files, and suspicious startup persistence."
- "Audit my open listening ports and active network connections—is anything risky exposed right now?"

### 2. MongoDB CTI Correlation & Remediation
- "Compare my live Windows security status against the threat findings stored in MongoDB and explain what has already been resolved versus what still needs monitoring."
- "Summarize the Windows CVEs in my CTI database (such as CVE-2024-38063 and CVE-2025-21298) and verify whether my current system configuration satisfies their remediations."
- "Which threat findings in MongoDB apply to Windows versus macOS, and how do my live host settings protect against the Windows ones?"

### 3. Live Hardware & Software Inventory Audit
- "Check my laptop's hardware specs and tell me if Docker, MongoDB, Python, and VS Code are installed."
- "Audit my installed developer tools and runtime versions on this machine—is anything missing for running a containerized AI backend?"

### 4. Multi-Turn Conversational Memory
1. "Scan my system for any security exposures or open ports."
2. "Based on what you just found on my machine, give me the top two PowerShell commands I should run to harden it further."

### 5. All-in-One Capstone Briefing
- "Give me a full security and system briefing: check my laptop specs and whether VS Code and Docker are installed, run a live Windows threat scan across Defender, firewall, ports, and secret files, and correlate the results with my MongoDB CTI findings."
