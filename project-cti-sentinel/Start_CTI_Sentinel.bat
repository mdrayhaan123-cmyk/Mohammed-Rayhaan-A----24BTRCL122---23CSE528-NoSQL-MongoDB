@echo off
title CTI Sentinel Server
cd /d "%~dp0"
set "GEMINI_MODEL=gemini-3.5-flash-lite"
start "CTI Sentinel Server" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { if ((Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200) { break } } catch {}; Start-Sleep -Milliseconds 500 }"
start "" "http://127.0.0.1:8000"
