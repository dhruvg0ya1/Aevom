import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules import contact_tracker


class TestContactTracker:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_file = contact_tracker.CONTACT_FILE
        contact_tracker.CONTACT_FILE = os.path.join(self.tmpdir, "contacts.json")

    def teardown_method(self):
        contact_tracker.CONTACT_FILE = self.orig_file

    def test_add_and_load_contact(self):
        c = contact_tracker.add_contact(
            company="Google",
            contact_name="John Doe",
            title="Recruiter",
            email="john@google.com",
            linkedin_url="https://linkedin.com/in/johndoe",
            notes="Met at career fair",
        )
        assert c["company"] == "Google"
        assert c["contact_name"] == "John Doe"
        assert c["status"] == "active"
        assert c["follow_up_count"] == 0
        assert c["id"] == 1
        loaded = contact_tracker.get_contact_by_email("john@google.com")
        assert loaded is not None
        assert loaded["company"] == "Google"

    def test_advance_follow_up(self):
        c = contact_tracker.add_contact(company="Anthropic", contact_name="Sarah", title="", email="s@anthropic.com")
        contact_tracker.advance_follow_up(c["id"])
        updated = contact_tracker.get_contact_by_email("s@anthropic.com")
        assert updated["follow_up_count"] == 1
        assert updated["status"] == "followed_up_1"
        assert updated["next_follow_up_date"] is not None

    def test_multiple_follow_ups(self):
        c = contact_tracker.add_contact(company="Meta", contact_name="Mark", title="", email="m@meta.com")
        contact_tracker.advance_follow_up(c["id"])
        contact_tracker.advance_follow_up(c["id"])
        contact_tracker.advance_follow_up(c["id"])
        updated = contact_tracker.get_contact_by_email("m@meta.com")
        assert updated["follow_up_count"] == 3
        assert updated["status"] == "followed_up_3"

    def test_mark_responded(self):
        c = contact_tracker.add_contact(company="OpenAI", contact_name="Sam", title="", email="s@openai.com")
        contact_tracker.mark_responded(c["id"])
        updated = contact_tracker.get_contact_by_email("s@openai.com")
        assert updated["status"] == "responded"
        assert updated["next_follow_up_date"] is None

    def test_mark_rejected(self):
        c = contact_tracker.add_contact(company="X", contact_name="Elon", title="", email="e@x.com")
        contact_tracker.mark_rejected(c["id"])
        assert contact_tracker.get_contact_by_email("e@x.com")["status"] == "rejected"

    def test_search_contacts(self):
        contact_tracker.add_contact(company="Google", contact_name="John", title="", email="j@google.com")
        contact_tracker.add_contact(company="Microsoft", contact_name="Jane", title="", email="j@microsoft.com")
        results = contact_tracker.search_contacts("google")
        assert len(results) == 1
        assert results[0]["company"] == "Google"
        results2 = contact_tracker.search_contacts("jane")
        assert len(results2) == 1
        assert results2[0]["contact_name"] == "Jane"
        all_results = contact_tracker.search_contacts("")
        assert len(all_results) == 2

    def test_get_recommended_next_action(self):
        c = contact_tracker.add_contact(company="Test", contact_name="Tester", title="", email="t@test.com")
        action = contact_tracker.get_recommended_next_action(c)
        assert "initial" in action.lower()
        contact_tracker.advance_follow_up(c["id"])
        c2 = contact_tracker.get_contact_by_email("t@test.com")
        action2 = contact_tracker.get_recommended_next_action(c2)
        assert "follow-up 2" in action2.lower()
        contact_tracker.mark_responded(c2["id"])
        c3 = contact_tracker.get_contact_by_email("t@test.com")
        action3 = contact_tracker.get_recommended_next_action(c3)
        assert "reply" in action3.lower()

    def test_log_outcome(self):
        c = contact_tracker.add_contact(company="C", contact_name="P", title="", email="p@c.com")
        contact_tracker.log_outcome(c["id"], "Hired elsewhere")
        updated = contact_tracker.get_contact_by_email("p@c.com")
        assert updated["status"] == "closed"
        assert updated["outcome"] == "Hired elsewhere"

    def test_get_contacts_due_for_follow_up(self):
        c = contact_tracker.add_contact(company="DueCo", contact_name="Due", title="", email="due@co.com")
        contact_tracker.advance_follow_up(c["id"])
        due = contact_tracker.get_contacts_due_for_follow_up()
        assert isinstance(due, list)
