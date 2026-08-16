import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules import enrichment


class TestEnrichment:
    def setup_method(self):
        enrichment.CACHE_DIR = tempfile.mkdtemp()
        enrichment.PERSON_CACHE_FILE = os.path.join(enrichment.CACHE_DIR, "person_cache.json")
        enrichment.COMPANY_CACHE_FILE = os.path.join(enrichment.CACHE_DIR, "company_cache.json")

    @patch("modules.enrichment.requests.get")
    def test_get_person_profile(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "public_identifier": "johndoe",
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "headline": "ML Engineer at Google",
            "summary": "Experienced engineer",
            "skills": ["Python", "ML"],
            "experiences": [
                {
                    "company": "Google",
                    "company_linkedin_profile_url": "https://linkedin.com/company/google",
                    "title": "ML Engineer",
                    "description": "Building ML models",
                    "ends_at": None,
                }
            ],
            "education": [{"degree": "BS CS", "school": "MIT"}],
            "personal_emails": ["john@gmail.com"],
            "personal_numbers": [],
            "extra": {},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = enrichment.get_person_profile(
            "https://linkedin.com/in/johndoe", "test_key"
        )
        assert result["full_name"] == "John Doe"
        assert result["first_name"] == "John"
        assert result["current_company"] == "Google"
        assert result["current_role"] == "ML Engineer"
        assert "Python" in result["skills"]
        mock_get.assert_called_once()

    @patch("modules.enrichment.requests.get")
    def test_get_person_profile_cached(self, mock_get):
        enrichment._cache_set(
            "person:https://linkedin.com/in/johndoe",
            {"full_name": "Cached User", "current_company": "Cached Co"},
            enrichment.PERSON_CACHE_FILE,
        )
        result = enrichment.get_person_profile(
            "https://linkedin.com/in/johndoe", "test_key"
        )
        assert result["full_name"] == "Cached User"
        mock_get.assert_not_called()

    @patch("modules.enrichment.requests.get")
    def test_resolve_company_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"url": "https://linkedin.com/company/google"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = enrichment.resolve_company_url("Google", "test_key")
        assert result == "https://linkedin.com/company/google"
        mock_get.assert_called_once()

    @patch("modules.enrichment.requests.get")
    def test_resolve_company_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"url": None}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = enrichment.resolve_company_url("NonExistentCompanyXYZ", "test_key")
        assert result is None

    @patch("modules.enrichment.requests.get")
    def test_get_company_profile(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "name": "Google",
            "description": "Search engine company",
            "website": "https://google.com",
            "industry": "Internet",
            "company_size": "10000+",
            "founded_year": 1998,
            "tagline": "Don't be evil",
            "specialities": ["Search", "Cloud"],
            "hq": {"city": "Mountain View", "country": "US"},
            "extra": {"total_funding_amount": 1000000000},
            "funding_data": [{"funding_type": "Series A"}],
            "updates": [{"text": "New product launch!", "posted_on": "2026-01-01"}],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = enrichment.get_company_profile(
            "https://linkedin.com/company/google", "test_key"
        )
        assert result["name"] == "Google"
        assert result["industry"] == "Internet"
        assert result["founded_year"] == 1998
        assert len(result["recent_updates"]) == 1
        mock_get.assert_called_once()

    @patch("modules.enrichment.requests.get")
    def test_person_profile_api_error(self, mock_get):
        mock_get.side_effect = Exception("API error")
        try:
            enrichment.get_person_profile(
                "https://linkedin.com/in/johndoe", "bad_key"
            )
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "API error" in str(e)

    def test_cache_persistence(self):
        enrichment._cache_set(
            "test_key_123", {"data": "test_value"}, enrichment.PERSON_CACHE_FILE
        )
        result = enrichment._cache_get("test_key_123", enrichment.PERSON_CACHE_FILE)
        assert result == {"data": "test_value"}

    def test_normalize_url(self):
        url = enrichment._normalize_url("HTTP://LINKEDIN.COM/IN/USER/")
        assert url == "https://linkedin.com/in/user"
