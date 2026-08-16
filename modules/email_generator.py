import json
import re
from huggingface_hub import InferenceClient

PROMPT_FILE = "prompts/cold_email_prompt.txt"

MODEL = "Qwen/Qwen3-32B"
TEMPERATURE = 0.4
MAX_TOKENS = 2500


def load_system_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def build_user_prompt(context):
    parts = []
    parts.append("CANDIDATE PROFILE:")
    parts.append("--- RESUME ---")
    parts.append(context.get("resume", "Not available"))
    parts.append("")
    parts.append("--- ADDITIONAL DETAILS ---")
    parts.append(context.get("additional_details", "Not available"))
    parts.append("")
    parts.append("RECIPIENT:")
    parts.append(f"Name: {context.get('recipient_name', 'Unknown')}")
    parts.append(f"Email: {context.get('recipient_email', 'Unknown')}")
    parts.append(f"Title: {context.get('recipient_title', 'Unknown')}")
    parts.append("")
    parts.append("HIRING COMPANY:")
    parts.append(f"Name: {context.get('hiring_company_name', 'Unknown')}")
    parts.append(f"Description: {context.get('company_description', 'Not available')}")
    parts.append(f"Industry: {context.get('company_industry', 'Unknown')}")
    parts.append(f"Stage: {context.get('company_stage', 'Unknown')}")
    parts.append(f"Recent Updates: {context.get('company_recent_updates', 'None')}")
    parts.append(f"Tagline: {context.get('company_tagline', 'None')}")
    parts.append(f"Specialities: {context.get('company_specialities', 'None')}")
    parts.append(f"Website: {context.get('company_website', 'Unknown')}")
    parts.append("")
    parts.append("RECRUITER / POSTER PROFILE:")
    parts.append(f"Name: {context.get('poster_name', 'Unknown')}")
    parts.append(f"Current Role: {context.get('poster_current_role', 'Unknown')}")
    parts.append(f"Headline: {context.get('poster_headline', 'Unknown')}")
    parts.append(f"Summary: {context.get('poster_summary', 'None')}")
    parts.append(f"Skills: {context.get('poster_skills', 'None')}")
    parts.append("")
    parts.append("JOB DESCRIPTION:")
    parts.append(context.get("job_description", "Not provided"))
    parts.append("")
    parts.append("ADDITIONAL CONTEXT:")
    parts.append(context.get("additional_context", "None"))
    parts.append("")
    parts.append(f"SOURCE TYPE: {context.get('source_type', 'manual_entry')}")
    parts.append("")
    parts.append("TEMPLATE GUIDANCE:")
    parts.append(
        "Based on the above, select the most appropriate template (T1-T9). "
        "Generate the primary email and all follow-ups. "
        "Output ONLY a valid JSON object. No markdown, no preamble."
    )
    return "\n".join(parts)


def call_llm(system_prompt, user_prompt, hf_token):
    client = InferenceClient(model=MODEL, token=hf_token)
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    raw = response.choices[0].message.content
    return raw


def _ensure_required_fields(result):
    required = [
        "primary_subject", "subject_variant_a", "subject_variant_b",
        "email_body", "followup_1", "followup_2", "followup_3",
        "personalization_notes", "flags",
    ]
    for key in required:
        if key not in result:
            result[key] = result.get(key, "")


def _extract_json_from_text(text):
    """Extract and parse a JSON object from within surrounding text."""
    brace_depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if start is None:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    start = None
    return None


def parse_llm_output(raw_text):
    """Try to parse JSON. Falls back to regex extraction."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # 1. Try direct JSON parse (handles clean output)
    try:
        result = json.loads(cleaned)
        _ensure_required_fields(result)
        return result
    except json.JSONDecodeError:
        pass

    # 2. Try to extract JSON object from within surrounding text
    result = _extract_json_from_text(cleaned)
    if result is not None:
        _ensure_required_fields(result)
        return result

    # 3. Fallback to regex extraction
    return _fallback_parse(cleaned)


def _fallback_parse(text):
    result = {
        "primary_subject": "",
        "subject_variant_a": "",
        "subject_variant_b": "",
        "email_body": "",
        "followup_1": "",
        "followup_2": "",
        "followup_3": "",
        "personalization_notes": "",
        "flags": [],
    }
    subject_match = re.search(
        r'(?:primary_subject|subject_variant[ab]|subject_line)\s*[:=]\s*"([^"]+)"',
        text, re.IGNORECASE
    )
    if subject_match:
        result["primary_subject"] = subject_match.group(1).strip()
    body_match = re.search(
        r'email_body\s*[:=]\s*"((?:[^"\\]|\\.)*)"',
        text, re.IGNORECASE | re.DOTALL
    )
    if body_match:
        result["email_body"] = body_match.group(1).strip()
    flags_match = re.search(r'flags\s*[:=]\s*(\[[^\]]*\])', text, re.IGNORECASE | re.DOTALL)
    if flags_match:
        raw_flags = flags_match.group(1)
        result["flags"] = [f.strip().strip('"\'') for f in raw_flags.split(",") if f.strip()]
    return result


def select_template(context):
    """Select most appropriate template T1-T9 based on context signals."""
    company_name = (context.get("hiring_company_name") or "").lower()
    industry = (context.get("company_industry") or "").lower()
    jd = (context.get("job_description") or "").lower()
    role = (context.get("recipient_title") or "").lower()
    role_type = (context.get("role_type") or "").lower()
    has_competing = bool(context.get("has_competing_offer"))
    has_alumni = bool(context.get("has_alumni_connection"))
    is_referral = bool(context.get("is_referral"))

    if is_referral:
        return "T7"
    if has_alumni:
        return "T9"
    if has_competing:
        return "T8"
    startup_keywords = ["startup", "seed", "series a", "early stage", "founder"]
    is_startup = any(kw in company_name or kw in industry for kw in startup_keywords)
    role_lower = role.lower()
    is_technical = any(
        kw in role_lower or kw in jd
        for kw in ["engineer", "ml", "data", "backend", "frontend", "full stack",
                   "software", "dev", "technical", "developer", "sde"]
    )
    is_finance = any(
        kw in role_lower or kw in jd or kw in industry
        for kw in ["finance", "consulting", "investment", "banking", "analyst",
                   "big 4", "big4", "consultant", "m&a", "advisory"]
    )
    is_generalist = any(
        kw in role_lower or kw in jd
        for kw in ["generalist", "founder's office", "chief of staff", "strategic",
                   "operations", "strategy intern"]
    )

    if is_startup and "intern" in role_lower or "intern" in jd:
        return "T1"
    if is_finance and "intern" in role_lower or "intern" in jd:
        return "T2"
    if is_generalist:
        return "T3"
    if is_technical:
        return "T5"
    if is_finance:
        return "T6"
    if is_startup:
        return "T1"
    return "T4"
