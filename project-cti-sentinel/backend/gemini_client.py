import os
import time
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.system_inspector import get_hardware_specs, get_installed_apps, run_live_threat_scan

load_dotenv(override=True)

_CACHED_MODELS: List[str] = []


def get_clean_api_key() -> str:
    raw = os.getenv("GEMINI_API_KEY", "")
    return raw.strip().strip('"').strip("'").strip()


def has_gemini_key() -> bool:
    return len(get_clean_api_key()) >= 20


def _discover_models(client: genai.Client) -> List[str]:
    global _CACHED_MODELS
    if _CACHED_MODELS:
        return _CACHED_MODELS

    skip_tokens = (
        "embedding", "imagen", "veo", "tts", "audio",
        "robotics", "computer-use", "deep-research", "image",
        "gemini-4-", "gemini-2.5-",
    )
    flash_lite, flash = [], []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "").strip()
            low = name.lower()
            actions = getattr(m, "supported_actions", []) or []
            if "gemini" not in low or any(t in low for t in skip_tokens):
                continue
            if actions and "generateContent" not in actions:
                continue
            if "flash-lite" in low:
                flash_lite.append(name)
            elif "flash" in low:
                flash.append(name)
    except Exception:
        pass

    pinned = os.getenv("GEMINI_MODEL", "").strip()
    ordered = list(dict.fromkeys(([pinned] if pinned else []) + flash_lite + flash))
    if ordered:
        _CACHED_MODELS = ordered
    return ordered or ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]


def _format_findings_context(findings: List[Dict[str, Any]]) -> str:
    if not findings:
        return "None"
    lines = []
    for f in findings[:25]:
        fid = f.get("id") or f.get("vuln_id") or "UNKNOWN"
        title = f.get("title", "Untitled")
        platform = f.get("platform", "All")
        status = f.get("lifecycle") or f.get("status", "Unknown")
        cve = f.get("cve", "N/A")
        summary = f.get("summary") or f.get("description", "")
        remediation = f.get("remediation") or f.get("mitigation", "")
        lines.append(
            f"- [{fid}] ({platform} | Lifecycle: {status} | CVE: {cve}) {title}: {summary} | Remediation: {remediation}"
        )
    return "\n".join(lines)


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "None"
    recent = history[-8:]
    return "\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in recent)


def ask_gemini_cti(
    question: str,
    findings: Optional[List[Dict[str, Any]]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    platform_filter: str = "ALL",
    lifecycle_filter: str = "ALL",
) -> Tuple[str, str]:
    api_key = get_clean_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing in .env")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30_000),
    )

    q_low = question.lower().strip()
    force_scan = any(
        k in q_low
        for k in ("scan", "threat", "vuln", "security", "virus", "malware", "port", "firewall", "defender", "verify", "audit", "check system")
    )
    needs_sys = force_scan or any(
        k in q_low
        for k in ("vs code", "vscode", "visual studio", "installed", "software", "app", "spec", "laptop", "ram", "cpu", "gpu", "windows", "docker", "python", "git")
    )

    live_specs = get_hardware_specs() if needs_sys else "Available on request"
    live_apps = get_installed_apps() if needs_sys else "Available on request"
    live_threats = run_live_threat_scan(force=force_scan) if force_scan else "Available on request"

    sys_msg = (
        "You are CTI Sentinel AI, a helpful conversational assistant with live read-access to the user's Windows system. "
        "Chat naturally and concisely like a normal assistant, matching the user's tone and length. "
        "Use LIVE HOST HARDWARE SPECS and LIVE INSTALLED SOFTWARE when asked about specs or installed apps, "
        "and analyze LIVE SYSTEM THREAT TELEMETRY alongside MongoDB findings when asked to check or scan threats."
    )
    prompt = (
        f"LIVE HOST HARDWARE SPECS:\n{live_specs}\n\n"
        f"LIVE INSTALLED SOFTWARE:\n{live_apps}\n\n"
        f"LIVE SYSTEM THREAT TELEMETRY:\n{live_threats}\n\n"
        f"MONGODB FINDINGS (Filters: {platform_filter}/{lifecycle_filter}):\n"
        f"{_format_findings_context(findings or [])}\n\n"
        f"HISTORY:\n{_format_history(history or [])}\n\n"
        f"USER: {question}"
    )

    errors: List[str] = []
    for model_name in _discover_models(client):
        for attempt in range(2):
            try:
                res = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_msg,
                        temperature=0.5,
                        max_output_tokens=1024,
                    ),
                )
                txt = (res.text or "").strip()
                if txt:
                    return txt, model_name
            except Exception as exc:
                err_s = str(exc)
                errors.append(f"{model_name} [try {attempt+1}]: {err_s}")
                if attempt == 0 and ("429" in err_s or "503" in err_s or "timed out" in err_s.lower() or "timeout" in err_s.lower()):
                    time.sleep(1.5)
                    continue
                break
    raise RuntimeError(" | ".join(errors[-4:]) if errors else "No compatible Gemini models responded.")
