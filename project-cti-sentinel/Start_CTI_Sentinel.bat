@echo off
cd /d "C:\Users\mdray\Downloads\Mongo experiments\cti-llm-capstone"
start "CTI Sentinel Server" cmd /k ""C:\Users\mdray\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { if ((Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200) { break } } catch {}; Start-Sleep -Milliseconds 500 }"
start "" "http://127.0.0.1:8000"
