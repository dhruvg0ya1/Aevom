import re
import difflib


def _build_math_normalize():
    """Build mapping of Unicode Mathematical Alphanumeric chars to ASCII."""
    mapping = {}
    # Each tuple: (start_cp, base_ascii, char_type)
    # char_type: 'upper', 'lower', 'digit'
    ranges = [
        # Mathematical Bold
        (0x1D400, 'A', 'upper'), (0x1D41A, 'a', 'lower'),
        # Mathematical Italic
        (0x1D434, 'A', 'upper'), (0x1D44E, 'a', 'lower'),
        # Mathematical Bold Italic
        (0x1D468, 'A', 'upper'), (0x1D482, 'a', 'lower'),
        # Mathematical Bold Script
        (0x1D4D0, 'A', 'upper'), (0x1D4EA, 'a', 'lower'),
        # Mathematical Bold Fraktur
        (0x1D56C, 'A', 'upper'), (0x1D586, 'a', 'lower'),
        # Mathematical Sans-Serif
        (0x1D5A0, 'A', 'upper'), (0x1D5BA, 'a', 'lower'),
        # Mathematical Sans-Serif Bold
        (0x1D5D4, 'A', 'upper'), (0x1D5EE, 'a', 'lower'),
        # Mathematical Sans-Serif Italic
        (0x1D608, 'A', 'upper'), (0x1D622, 'a', 'lower'),
        # Mathematical Monospace
        (0x1D670, 'A', 'upper'), (0x1D68A, 'a', 'lower'),
        # Digits
        (0x1D7CE, '0', 'digit'),  # Bold
        (0x1D7D8, '0', 'digit'),  # Double-struck
        (0x1D7E2, '0', 'digit'),  # Sans-serif
        (0x1D7EC, '0', 'digit'),  # Sans-serif Bold
        (0x1D7F6, '0', 'digit'),  # Monospace
    ]
    # Math Fraktur only has uppercase A-M (incomplete block), skip it
    for start_cp, base, ctype in ranges:
        if ctype == 'digit':
            for i in range(10):
                mapping[start_cp + i] = chr(ord(base) + i)
        else:
            for i in range(26):
                mapping[start_cp + i] = chr(ord(base) + i)
    return mapping


_MATH_NORMALIZE = _build_math_normalize()


def normalize_unicode_text(text):
    """Convert Unicode mathematical bold/italic/sans chars to ASCII."""
    if not text:
        return text
    result = []
    for ch in text:
        result.append(_MATH_NORMALIZE.get(ord(ch), ch))
    return ''.join(result)


EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

LINKEDIN_PATTERNS = {
    "profile": re.compile(r"https?://(www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE),
    "company": re.compile(r"https?://(www\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE),
    "post": re.compile(r"https?://(www\.)?linkedin\.com/posts/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE),
    "update": re.compile(r"https?://(www\.)?linkedin\.com/feed/update/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE),
    "pulse": re.compile(r"https?://(www\.)?linkedin\.com/pulse/[a-zA-Z0-9\-_%]+/?", re.IGNORECASE),
}

FORBIDDEN_PHRASES = [
    "I hope this email finds you well",
    "I am writing to inquire",
    "I am writing to express",
    "Dear Sir/Madam",
    "To Whom It May Concern",
    "Kindly",
    "Esteemed",
    "Humble",
    "I have always been fascinated",
    "I look forward to hearing from you",
]

SUBJECT_FORBIDDEN = [
    "Quick Question",
    "Hello",
    "Greetings",
    "Internship Application",
    "Opportunity",
]

PREFIX_DOMAINS = [
    "careers", "jobs", "hr", "info", "talent", "apply",
    "recruiting", "no-reply", "noreply", "contact", "hello", "team",
]

LEGAL_SUFFIXES = [
    "inc", "llc", "ltd", "corp", "co", "company", "corporation",
    "group", "technologies", "tech", "platforms", "limited",
    "private limited", "pvt ltd", "inc.", "llc.", "ltd.",
]

TITLE_PATTERNS = [
    r"(?i)(?:role|position|title|hiring for|looking for|seeking)\s*(?:a|an)?\s*:?\s*([A-Z][A-Za-z\s/&]+)",
    r"(?i)(?:as\s+(?:a|an)?\s*)([A-Z][A-Za-z\s/&]+?)(?:\s+(?:at|in|with|for|–|—|-)\s|$)",
]

ROLE_KEYWORDS = {
    "internship": ["intern", "internship", "internship program", "summer intern"],
    "full-time": ["full time", "full-time", "ft", "permanent"],
    "contract": ["contract", "freelance", "gig", "temporary"],
    "co-founder": ["co-founder", "cofounder", "founding"],
    "part-time": ["part time", "part-time", "pt"],
}

SENIORITY_KEYWORDS = {
    "entry": ["junior", "jr", "graduate", "associate", "entry", "new grad"],
    "mid": ["mid", "mid-level", "level 2", "ii"],
    "senior": ["senior", "sr", "staff", "principal", "lead"],
    "director": ["director", "head of", "vp of", "vice president"],
    "executive": ["cfo", "cto", "ceo", "coo", "chief", "cxo"],
}

COMPANY_INDICATORS = [
    r"(?i)(?:at|for|with|join)\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+(?:is|are|we|inc|llc|ltd|corp)|\.|,|$)",
    r"(?i)([A-Z][A-Za-z0-9]+(?:[.\s][A-Z][A-Za-z0-9]+)*?(?:Inc|LLC|Ltd|Corp|Technologies|Tech|AI|Labs))\b",
]


def extract_email(text):
    """Extract first email address from text."""
    if not text:
        return None
    match = re.search(EMAIL_REGEX, normalize_unicode_text(text))
    return match.group(0) if match else None


def extract_all_emails(text):
    """Extract all email addresses from text."""
    if not text:
        return []
    return re.findall(EMAIL_REGEX, normalize_unicode_text(text))


def classify_linkedin_url(url):
    """Classify a LinkedIn URL as profile, company, post, update, pulse, or None."""
    if not url:
        return None
    for kind, pattern in LINKEDIN_PATTERNS.items():
        if pattern.search(url):
            return kind
    return None


def extract_linkedin_url(text):
    """Extract first LinkedIn URL from text."""
    if not text:
        return None, None
    for kind, pattern in LINKEDIN_PATTERNS.items():
        match = pattern.search(text)
        if match:
            return match.group(0), kind
    return None, None


def extract_all_linkedin_urls(text):
    """Extract all LinkedIn URLs from text with their types."""
    if not text:
        return []
    found = []
    for kind, pattern in LINKEDIN_PATTERNS.items():
        for match in pattern.finditer(text):
            found.append((match.group(0), kind))
    return found


def company_name_from_email_domain(email):
    """Infer company name from email domain, stripping common prefixes."""
    if not email:
        return None
    match = re.search(r"@([a-zA-Z0-9.-]+)", email)
    if not match:
        return None
    domain = match.group(1).lower()
    domain = domain.replace("www.", "")
    parts = domain.split(".")
    if len(parts) >= 2:
        name_part = parts[0]
        for prefix in PREFIX_DOMAINS:
            if name_part.startswith(prefix) and len(name_part) > len(prefix):
                rest = name_part[len(prefix):]
                if rest.startswith("-") or rest.startswith("."):
                    name_part = rest[1:]
                else:
                    name_part = rest
                break
        return name_part.capitalize()
    return None


def normalize_company_name(name):
    """Normalize company name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    for suffix in LEGAL_SUFFIXES:
        suffix_pattern = r"\s*[.,]?\s*" + re.escape(suffix) + r"[.,]?\s*$"
        name = re.sub(suffix_pattern, "", name)
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def match_company_names(name1, name2):
    """Compare two company names and return confidence score 0-100."""
    if not name1 or not name2:
        return 0
    n1 = normalize_company_name(name1)
    n2 = normalize_company_name(name2)
    if not n1 or not n2:
        return 0
    if n1 == n2:
        return 100
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    if ratio >= 0.95:
        return 95
    if ratio >= 0.80:
        return 80
    if ratio >= 0.60:
        return 60
    return int(ratio * 100)


def extract_recruiter_name(text):
    """Extract person name from intro patterns."""
    if not text:
        return None
    patterns = [
        r"(?i)(?:I'm|I am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        r"(?i)(?:my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        r"(?i)^([A-Z][a-z]+(?:\s+[A-Z][a-z]+))\s*[,|]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def extract_company_mentions(text):
    """Find all company-like mentions in text."""
    if not text:
        return []
    mentions = set()
    for pattern in COMPANY_INDICATORS:
        matches = re.findall(pattern, text)
        for m in matches:
            cleaned = m.strip().rstrip(".,!?:;")
            if cleaned and len(cleaned) > 1:
                mentions.add(cleaned)
    return list(mentions)


def extract_hiring_company(text):
    """Extract hiring company from job description or post text."""
    if not text:
        return None
    patterns = [
        r"(?i)(?:at|for|with|join)\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+(?:is\s+hiring|are\s+hiring|we're|we\s+are|is\s+looking|seeking|–|—|-)|\.)",
        r"(?i)(?:role\s+(?:at|with|in))\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+–|\s+—|\.)",
        r"(?i)(?:position\s+(?:at|with|in))\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+–|\s+—|\.)",
        r"(?i)(?:job\s+(?:at|with|in))\s+([A-Z][A-Za-z0-9\s&.]+?)(?:\s+–|\s+—|\.)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip().rstrip(".,!?:;")
            if len(company) > 1:
                return company
    return None


def extract_job_title(text):
    """Extract job title from text."""
    if not text:
        return None
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            title = match.group(1).strip().rstrip(".,!?:;")
            if len(title) > 2:
                return title
    return None


def extract_job_description_section(text):
    """Try to extract the job description block from pasted text."""
    if not text:
        return None
    sections = []
    markers = [
        r"(?i)(?:job description|about the role|the role|responsibilities|requirements|what you'll do|what we're looking for|about you|qualifications).*?(?:\n|$)(.*?)(?=\n\n|\Z)",
        r"(?i)(?:we are hiring|we're hiring|hiring for|looking for).*?(?:\n|$)(.*?)(?=\n\n|\Z)",
    ]
    for marker in markers:
        matches = re.findall(marker, text, re.DOTALL)
        sections.extend(matches)
    if sections:
        longest = max(sections, key=len).strip()
        if len(longest) > 50:
            return longest
    if len(text) > 100:
        return text[:2000]
    return None


def extract_role_type(text):
    """Classify role type from text."""
    if not text:
        return None
    text_lower = text.lower()
    for role_type, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return role_type
    return None


def extract_seniority(text):
    """Classify seniority level from text."""
    if not text:
        return None
    text_lower = text.lower()
    for level, keywords in SENIORITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return level
    return None


def extract_all_entities(text):
    """Run all extractors and return unified dict of found entities."""
    if not text:
        return {}
    text = normalize_unicode_text(text)
    urls_with_types = extract_all_linkedin_urls(text)
    first_profile = None
    first_company = None
    for url, kind in urls_with_types:
        if kind == "profile" and not first_profile:
            first_profile = url
        if kind == "company" and not first_company:
            first_company = url
    return {
        "emails": extract_all_emails(text),
        "primary_email": extract_email(text),
        "linkedin_urls": [u for u, _ in urls_with_types],
        "linkedin_profile_url": first_profile,
        "linkedin_company_url": first_company,
        "recruiter_name": extract_recruiter_name(text),
        "company_mentions": extract_company_mentions(text),
        "hiring_company": extract_hiring_company(text),
        "job_title": extract_job_title(text),
        "job_description": extract_job_description_section(text),
        "role_type": extract_role_type(text),
        "seniority": extract_seniority(text),
    }


def check_forbidden_phrases(text, check_subject=False):
    """Scan text for forbidden phrases. Returns list of found phrases."""
    if not text:
        return []
    found = []
    text_lower = text.lower()
    phrases = FORBIDDEN_PHRASES
    if check_subject:
        phrases = SUBJECT_FORBIDDEN
    for phrase in phrases:
        if phrase.lower() in text_lower:
            found.append(phrase)
    return found


def check_subject_length(subject):
    """Check subject line length, return (char_count, warning)."""
    if not subject:
        return 0, "Subject is empty"
    count = len(subject)
    warning = None
    if count > 60:
        warning = f"Subject is {count} characters — aim for under 60 for mobile readability."
    elif count < 10:
        warning = f"Subject is only {count} characters — consider making it more specific."
    return count, warning


def count_words(text):
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())


def run_pre_send_checklist(subject, body, recipient_name=None):
    """Run automated pre-send checks, return dict of pass/fail."""
    checks = {}
    checks["subject_names_role"] = bool(subject and any(
        kw in subject.lower() for kw in ["role", "position", "internship", "interested",
                                          "application", "question", "alum", "alumnus"]
    ))
    checks["subject_under_60"] = len(subject or "") <= 60
    checks["subject_not_forbidden"] = not check_forbidden_phrases(subject, check_subject=True)
    checks["body_under_125"] = count_words(body) <= 125
    checks["body_no_forbidden"] = not check_forbidden_phrases(body)
    checks["body_no_hopeful"] = "i hope this email" not in (body or "").lower()
    checks["body_no_multiple_asks"] = len(re.findall(
        r"(?i)(?:would you|can you|could you|are you)", body or ""
    )) <= 2
    checks["recipient_name_spelled"] = bool(recipient_name) and (
        recipient_name.lower() in (body or "").lower()
    )
    return checks
