import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules import utils


def test_extract_email():
    assert utils.extract_email("hello@world.com") == "hello@world.com"
    assert utils.extract_email("Contact me at john@example.com") == "john@example.com"
    assert utils.extract_email("No email here") is None
    assert utils.extract_email("") is None
    assert utils.extract_email("Multiple test@one.com and test2@two.com") == "test@one.com"


def test_extract_all_emails():
    result = utils.extract_all_emails("a@b.com c@d.com")
    assert len(result) == 2
    assert "a@b.com" in result
    assert "c@d.com" in result
    assert utils.extract_all_emails("") == []


def test_classify_linkedin_url():
    assert utils.classify_linkedin_url("https://linkedin.com/in/johndoe") == "profile"
    assert utils.classify_linkedin_url("https://www.linkedin.com/in/jane-smith/") == "profile"
    assert utils.classify_linkedin_url("https://linkedin.com/company/acme") == "company"
    assert utils.classify_linkedin_url("https://linkedin.com/posts/some-post") == "post"
    assert utils.classify_linkedin_url("https://linkedin.com/feed/update/123") == "update"
    assert utils.classify_linkedin_url("https://linkedin.com/pulse/article") == "pulse"
    assert utils.classify_linkedin_url("https://google.com") is None
    assert utils.classify_linkedin_url("") is None


def test_extract_linkedin_url():
    text = "Check out https://linkedin.com/in/johndoe for details"
    url, kind = utils.extract_linkedin_url(text)
    assert url == "https://linkedin.com/in/johndoe"
    assert kind == "profile"
    url2, kind2 = utils.extract_linkedin_url("No linkedin here")
    assert url2 is None and kind2 is None


def test_all_linkedin_patterns():
    text = (
        "Profile: https://linkedin.com/in/user "
        "Company: https://linkedin.com/company/acme "
        "Post: https://linkedin.com/posts/123 "
        "Update: https://linkedin.com/feed/update/abc "
        "Pulse: https://linkedin.com/pulse/article"
    )
    results = utils.extract_all_linkedin_urls(text)
    assert len(results) >= 5
    types = [t for _, t in results]
    assert "profile" in types
    assert "company" in types
    assert "post" in types
    assert "update" in types
    assert "pulse" in types


def test_company_name_from_email_domain():
    assert utils.company_name_from_email_domain("careers@openai.com") == "Openai"
    assert utils.company_name_from_email_domain("hr@google.com") == "Google"
    assert utils.company_name_from_email_domain("jobs@microsoft.com") == "Microsoft"
    assert utils.company_name_from_email_domain("info@stripe.com") == "Stripe"
    assert utils.company_name_from_email_domain("") is None
    assert utils.company_name_from_email_domain("notanemail") is None


def test_normalize_company_name():
    assert utils.normalize_company_name("Google Inc.") == "google"
    assert utils.normalize_company_name("Meta Platforms, Inc.") == "meta"
    assert utils.normalize_company_name("Anthropic") == "anthropic"
    assert utils.normalize_company_name("OpenAI LLC") == "openai"
    assert utils.normalize_company_name("") == ""
    assert utils.normalize_company_name(None) == ""


def test_match_company_names():
    assert utils.match_company_names("Google", "Google") == 100
    assert utils.match_company_names("Google Inc.", "Google LLC") >= 80
    assert utils.match_company_names("Meta", "Meta Platforms") >= 60
    assert utils.match_company_names("Google", "Microsoft") < 60
    assert utils.match_company_names("", "Something") == 0
    assert utils.match_company_names(None, None) == 0


def test_extract_recruiter_name():
    assert utils.extract_recruiter_name("I'm John Smith, recruiter at...") == "John Smith"
    assert utils.extract_recruiter_name("Hi, this is Jane Doe") == "Jane Doe"
    assert utils.extract_recruiter_name("My name is Alice Wonderland") == "Alice Wonderland"
    assert utils.extract_recruiter_name("No name pattern here") is None
    assert utils.extract_recruiter_name("") is None


def test_extract_company_mentions():
    result = utils.extract_company_mentions("Join Google for a great career")
    assert len(result) > 0
    result2 = utils.extract_company_mentions("")
    assert result2 == []


def test_extract_hiring_company():
    text = "We are hiring ML Engineers at Anthropic. Apply now!"
    assert utils.extract_hiring_company(text) is not None
    result = utils.extract_hiring_company("")
    assert result is None


def test_extract_job_title():
    text = "We are looking for a Senior ML Engineer"
    assert utils.extract_job_title(text) is not None
    assert utils.extract_job_title("") is None


def test_check_forbidden_phrases():
    body = "I hope this email finds you well. Kindly let me know."
    found = utils.check_forbidden_phrases(body)
    assert "I hope this email finds you well" in found
    assert "Kindly" in found
    clean = "Hi Sarah, I saw your post about the ML team."
    assert utils.check_forbidden_phrases(clean) == []


def test_check_subject_length():
    count, warning = utils.check_subject_length("Short subject")
    assert count == 13
    assert warning is None
    count2, warning2 = utils.check_subject_length("A" * 61)
    assert count2 == 61
    assert "60" in warning2
    count3, warning3 = utils.check_subject_length("A" * 45)
    assert count3 == 45
    assert warning3 is None


def test_count_words():
    assert utils.count_words("Hello world") == 2
    assert utils.count_words("") == 0
    assert utils.count_words("One two three four five") == 5


def test_run_pre_send_checklist():
    subject = "ML Engineer Interested in Role at Google"
    body = "Hi Sarah, I saw your post about the ML team. I have 3 years experience. Would you have 15 minutes?"
    checks = utils.run_pre_send_checklist(subject, body, "Sarah")
    assert isinstance(checks, dict)
    assert "subject_under_60" in checks
    assert "body_under_125" in checks
    assert "body_no_forbidden" in checks
    assert "recipient_name_spelled" in checks


def test_extract_role_type():
    assert utils.extract_role_type("Summer internship program") == "internship"
    assert utils.extract_role_type("Full-time position") == "full-time"
    assert utils.extract_role_type("") is None


def test_extract_seniority():
    assert utils.extract_seniority("Senior Engineer") == "senior"
    assert utils.extract_seniority("Junior Developer") == "entry"
    assert utils.extract_seniority("") is None
