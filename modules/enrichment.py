import os
import json
import requests

CACHE_DIR = "cache"
PERSON_CACHE_FILE = os.path.join(CACHE_DIR, "person_cache.json")
COMPANY_CACHE_FILE = os.path.join(CACHE_DIR, "company_cache.json")

PERSON_PROFILE_URL = "https://proxycurl.p.rapidapi.com/api/v2/linkedin"
COMPANY_RESOLVE_URL = "https://proxycurl.p.rapidapi.com/api/linkedin/company/resolve"
COMPANY_PROFILE_URL = "https://proxycurl.p.rapidapi.com/api/linkedin/company"


def _load_cache(cache_file):
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache_file, cache_dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_dict, f, indent=2)


def _cache_get(key, cache_file):
    c = _load_cache(cache_file)
    return c.get(key)


def _cache_set(key, value, cache_file):
    c = _load_cache(cache_file)
    c[key] = value
    _save_cache(cache_file, c)


def _normalize_url(url):
    url = url.strip().rstrip("/").lower()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def _build_headers(api_key):
    return {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "proxycurl.p.rapidapi.com",
        "Content-Type": "application/json",
    }


def get_person_profile(linkedin_url, api_key):
    """Fetch person profile from Proxycurl. Returns structured dict or None."""
    normalized = _normalize_url(linkedin_url)
    cache_key = f"person:{normalized}"
    cached = _cache_get(cache_key, PERSON_CACHE_FILE)
    if cached:
        return cached
    params = {
        "url": linkedin_url,
        "personal_contact_number": "include",
        "github_profile_id": "include",
        "personal_email": "include",
        "use_cache": "if-present",
        "facebook_profile_id": "include",
        "inferred_salary": "include",
        "extra": "include",
        "twitter_profile_id": "include",
        "fallback_to_cache": "on-error",
        "skills": "include",
    }
    try:
        resp = requests.get(
            PERSON_PROFILE_URL,
            headers=_build_headers(api_key),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Proxycurl Person Profile API error: {e}")
    profile = _extract_person_data(data)
    if profile:
        _cache_set(cache_key, profile, PERSON_CACHE_FILE)
    return profile


def _extract_person_data(data):
    if not data or data.get("public_identifier") is None:
        return None
    current_exp = None
    for exp in data.get("experiences", []):
        if exp.get("ends_at") is None:
            current_exp = exp
            break
    return {
        "full_name": data.get("full_name"),
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "headline": data.get("headline"),
        "summary": data.get("summary"),
        "occupation": data.get("occupation"),
        "current_company": current_exp.get("company") if current_exp else None,
        "current_company_linkedin_url": current_exp.get("company_linkedin_profile_url") if current_exp else None,
        "current_role": current_exp.get("title") if current_exp else None,
        "current_role_description": current_exp.get("description") if current_exp else None,
        "education": data.get("education", []),
        "skills": data.get("skills", []),
        "personal_emails": data.get("personal_emails", []),
        "personal_numbers": data.get("personal_numbers", []),
        "github": (data.get("extra") or {}).get("github_profile_id"),
        "twitter": (data.get("extra") or {}).get("twitter_profile_id"),
        "accomplishments": {
            "publications": data.get("accomplishment_publications", []),
            "honors": data.get("accomplishment_honors_awards", []),
            "projects": data.get("accomplishment_projects", []),
        },
    }


def resolve_company_url(company_name, api_key, domain=None):
    """Resolve company name to LinkedIn company URL. Returns URL string or None."""
    normalized = company_name.lower().strip()
    cache_key = f"resolve:{normalized}"
    cached = _cache_get(cache_key, COMPANY_CACHE_FILE)
    if cached:
        return cached
    params = {"company_name": company_name}
    if domain:
        params["company_domain"] = domain
    try:
        resp = requests.get(
            COMPANY_RESOLVE_URL,
            headers=_build_headers(api_key),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        url = data.get("url")
    except Exception as e:
        raise RuntimeError(f"Proxycurl Company Resolve API error: {e}")
    if url:
        _cache_set(cache_key, url, COMPANY_CACHE_FILE)
    return url


def get_company_profile(company_linkedin_url, api_key):
    """Fetch company profile from Proxycurl. Returns structured dict or None."""
    normalized = _normalize_url(company_linkedin_url)
    cache_key = f"company:{normalized}"
    cached = _cache_get(cache_key, COMPANY_CACHE_FILE)
    if cached:
        return cached
    params = {
        "url": company_linkedin_url,
        "extra": "include",
        "resolve_numeric_id": "true",
        "funding_data": "include",
        "acquisitions": "include",
        "use_cache": "if-present",
        "exit_data": "include",
        "categories": "include",
    }
    try:
        resp = requests.get(
            COMPANY_PROFILE_URL,
            headers=_build_headers(api_key),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Proxycurl Company Profile API error: {e}")
    profile = _extract_company_data(data)
    if profile:
        _cache_set(cache_key, profile, COMPANY_CACHE_FILE)
    return profile


def _extract_company_data(data):
    if not data or not data.get("name"):
        return None
    extra = data.get("extra") or {}
    recent_updates = []
    for update in (data.get("updates") or [])[:2]:
        recent_updates.append({
            "text": update.get("text", ""),
            "posted_on": update.get("posted_on", ""),
        })
    funding = data.get("funding_data") or []
    latest_round = funding[-1] if funding else None
    funding_stage = latest_round.get("funding_type") if latest_round else None
    return {
        "name": data.get("name"),
        "description": data.get("description"),
        "website": data.get("website"),
        "industry": data.get("industry"),
        "company_size": data.get("company_size"),
        "founded_year": data.get("founded_year"),
        "tagline": data.get("tagline"),
        "specialities": data.get("specialities", []),
        "hq": data.get("hq"),
        "recent_updates": recent_updates,
        "funding_data": funding,
        "funding_stage": funding_stage,
        "total_funding": extra.get("total_funding_amount"),
        "ipo_status": extra.get("ipo_status"),
        "operating_status": extra.get("operating_status"),
    }
