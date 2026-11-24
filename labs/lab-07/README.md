# Cyber Threat Intelligence (CTI) Platform — Lab 7.1 & 7.2

Consolidates **Lab 7.1 (Production Schema Analysis)** and **Lab 7.2 (Working Set & WiredTiger Cache Analysis)** into a full-stack Cyber Threat Intelligence platform backed by MongoDB (`lab_7` database).

## Quick Start (VS Code)

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
2. Ensure local MongoDB is running at `mongodb://localhost:27017`.
3. Seed the CTI database and run the Lab 7 scripts:
   ```powershell
   python backend/seed_cti_data.py
   python Lab_7_1/lab_7_1.py
   python Lab_7_1_Try_It_Yourself/lab_7_1_try_it_yourself.py
   python Lab_7_2/lab_7_2.py
   python Lab_7_2_Try_It_Yourself/lab_7_2_try_it_yourself.py
   ```
4. Launch the CTI Web Platform (FastAPI + Frontend):
   ```powershell
   uvicorn backend.app:app --reload --port 8000
   ```
   Open `http://127.0.0.1:8000` in your browser to search threats, classify indicators, inspect `$bsonSize` schema metrics, and monitor WiredTiger cache hit ratios.

## Live Web Interface
- **Live CTI Sentinel Dashboard:** [http://127.0.0.1:8080/?lab=7](http://127.0.0.1:8080/?lab=7)

## CTI Sentinel Integration & Verification Reference
- **Active LLM Model (`GEMINI_MODEL`):** `gemini-3.5-flash-lite` (configured in `.env` for free-tier quota stability).
- **Live Telemetry & MongoDB RAG Check:** Run `"Give me a full security and system briefing: check my laptop specs and whether VS Code and Docker are installed, run a live Windows threat scan across Defender, firewall, ports, and secret files, and correlate the results with my MongoDB CTI findings."` in CTI Sentinel (`http://127.0.0.1:8000`).
