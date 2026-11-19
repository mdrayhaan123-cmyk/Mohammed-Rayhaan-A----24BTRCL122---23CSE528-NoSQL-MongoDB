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
        return "No scanner or knowledge-base records currently loaded."
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

    client = genai.Client(api_key=api_key)

    system_instruction = (
        "You are CTI Sentinel AI, a responsive, intelligent cybersecurity and general-purpose assistant. "
        "CRITICAL RULES:\n"
        "1. Answer EVERY question and sub-question the user asks completely, clearly, and directly—whether it is "
        "a general knowledge question, programming/academic topic, cybersecurity concept, or a CTI/system audit query.\n"
        "2. When scanner findings or MongoDB knowledge-base records are provided, cite exact IDs (e.g., VULN-WIN-101), "
        "CVE numbers, exact remediation commands, and clearly state whether any unresolved/active risks remain.\n"
        "3. Use clean Markdown with bullet points and code blocks for commands."
    )

    prompt = f"""ACTIVE UI FILTERS: Platform={platform_filter}, Lifecycle={lifecycle_filter}

MONGODB KNOWLEDGE BASE & LIVE SYSTEM SCANNER FINDINGS:
{_format_findings_context(findings or [])}

RECENT CONVERSATION HISTORY:
{_format_history(history or [])}

USER QUESTION (answer every part thoroughly):
{question}
"""

    last_error = "No compatible Gemini models responded."

    for model_name in dict.fromkeys([m for m in FAST_MODELS if m]):
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.35,
                        max_output_tokens=1400,
                    ),
                )
                text = (response.text or "").strip()
                if text:
                    return text, model_name
            except Exception as exc:
                last_error = f"{model_name}: {exc}"
                if "429" in str(exc) or "503" in str(exc):
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break

    raise RuntimeError(last_error)
