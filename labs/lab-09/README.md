# Lab 9: Write Concern Latency & Network Partition (Docker Hub Submission)

## 1. Build & Push to Docker Hub
```powershell
docker build -t <your-dockerhub-username>/nosql-lab-09:latest .
docker login
docker push <your-dockerhub-username>/nosql-lab-09:latest
```

## 2. Run for Demonstration
```powershell
docker run --rm -e MONGO_URI=mongodb://host.docker.internal:27017 <your-dockerhub-username>/nosql-lab-09:latest
```

## Live Web Interface
- **Live CTI Sentinel Dashboard:** [http://127.0.0.1:8080/?lab=9](http://127.0.0.1:8080/?lab=9)

## CTI Sentinel Integration & Verification Reference
- **Active LLM Model (`GEMINI_MODEL`):** `gemini-3.5-flash-lite` (configured in `.env` for free-tier quota stability).
- **Live Telemetry & MongoDB RAG Check:** Run `"Give me a full security and system briefing: check my laptop specs and whether VS Code and Docker are installed, run a live Windows threat scan across Defender, firewall, ports, and secret files, and correlate the results with my MongoDB CTI findings."` in CTI Sentinel (`http://127.0.0.1:8000`).
