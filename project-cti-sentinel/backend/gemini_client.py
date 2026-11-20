import os
import time
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)

FAST_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip(),
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


def get_clean_api_key() -> str:
    raw = os.getenv("GEMINI_API_KEY", "")
    return raw.strip().strip('"').strip("'").strip()


def has_gemini_key() -> bool:
    return len(get_clean_api_key()) >= 20


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


from backend.system_inspector import get_hardware_specs, run_live_threat_scan

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
    client = genai.Client(api_key=api_key)

    q_low = question.lower()
    force_scan = any(k in q_low for k in ("scan", "threat", "vuln", "security", "virus", "malware", "port", "firewall", "defender", "verify", "audit", "check system"))
    live_specs = get_hardware_specs()
    live_threats = run_live_threat_scan(force=force_scan)

    sys_msg = (
        "You are CTI Sentinel AI, a natural, helpful assistant with live read-access to the user's Windows system. "
        "Chat naturally and concisely like a normal chatbot, matching the user's length and tone. "
        "Do NOT dump giant audit tables unless the user asks for a full system threat verification/audit. "
        "If the user asks about their laptop/PC specs, answer directly using LIVE HOST HARDWARE SPECS. "
        "If the user asks to verify threats or check system security, analyze LIVE SYSTEM THREAT TELEMETRY "
        "(ports, external connections, Defender, Firewall, ExecutionPolicy, RDP/SMB, startup items, secret files) "
        "alongside any relevant MongoDB findings, clearly flagging real risks vs safe controls."
    )
    prompt = (
        f"LIVE HOST HARDWARE SPECS:\n{live_specs}\n\n"
        f"LIVE SYSTEM THREAT TELEMETRY:\n{live_threats}\n\n"
        f"MONGODB FINDINGS (Filters: {platform_filter}/{lifecycle_filter}):\n"
        f"{_format_findings_context(findings or [])}\n\n"
        f"HISTORY:\n{_format_history(history or [])}\n\n"
        f"USER: {question}"
    )
    last_err = "No compatible Gemini models responded."
    for model_name in dict.fromkeys([m for m in FAST_MODELS if m]):
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
                last_err = f"{model_name}: {exc}"
                if "429" in str(exc) or "503" in str(exc):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
    raise RuntimeError(last_err)
