@echo off
title CTI Sentinel - Live Threat Intelligence & LLM Backend
cd /d "%~dp0"
set "GEMINI_MODEL=gemini-3.5-flash-lite"
start "" "http://127.0.0.1:8000"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
