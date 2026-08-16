import os
import json
from datetime import datetime, timedelta

CONTACT_FILE = "contact_tracker.json"


def _load():
    if not os.path.exists(CONTACT_FILE):
        return []
    try:
        with open(CONTACT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def _save(contacts):
    with open(CONTACT_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2)


def _new_id(contacts):
    ids = [c.get("id", 0) for c in contacts]
    return max(ids, default=0) + 1


def add_contact(company, contact_name, title, email, linkedin_url="", notes=""):
    contacts = _load()
    now = datetime.utcnow().isoformat()
    contact = {
        "id": _new_id(contacts),
        "company": company,
        "contact_name": contact_name,
        "title": title,
        "email": email,
        "linkedin_url": linkedin_url,
        "status": "active",
        "follow_up_count": 0,
        "last_contact_date": now[:10],
        "next_follow_up_date": None,
        "notes": notes,
        "outcome": "",
        "created_at": now,
        "updated_at": now,
    }
    contacts.append(contact)
    _save(contacts)
    return contact


def update_contact(contact_id, **fields):
    contacts = _load()
    for contact in contacts:
        if contact.get("id") == contact_id:
            for key, value in fields.items():
                if key in contact:
                    contact[key] = value
            contact["updated_at"] = datetime.utcnow().isoformat()
            break
    _save(contacts)


def advance_follow_up(contact_id):
    contacts = _load()
    for contact in contacts:
        if contact.get("id") == contact_id:
            contact["follow_up_count"] = contact.get("follow_up_count", 0) + 1
            count = contact["follow_up_count"]
            if count == 1:
                contact["status"] = "followed_up_1"
                contact["next_follow_up_date"] = (
                    datetime.utcnow() + timedelta(days=3)
                ).strftime("%Y-%m-%d")
            elif count == 2:
                contact["status"] = "followed_up_2"
                contact["next_follow_up_date"] = (
                    datetime.utcnow() + timedelta(days=4)
                ).strftime("%Y-%m-%d")
            elif count == 3:
                contact["status"] = "followed_up_3"
                contact["next_follow_up_date"] = (
                    datetime.utcnow() + timedelta(days=6)
                ).strftime("%Y-%m-%d")
            else:
                contact["status"] = "closed"
                contact["next_follow_up_date"] = None
            contact["updated_at"] = datetime.utcnow().isoformat()
            break
    _save(contacts)


def mark_responded(contact_id):
    update_contact(contact_id, status="responded", next_follow_up_date=None)


def mark_scheduled_call(contact_id):
    update_contact(contact_id, status="scheduled_call", next_follow_up_date=None)


def mark_rejected(contact_id):
    update_contact(contact_id, status="rejected", next_follow_up_date=None)


def mark_closed(contact_id):
    update_contact(contact_id, status="closed", next_follow_up_date=None)


def get_contact_by_email(email):
    contacts = _load()
    for c in contacts:
        if c.get("email", "").lower() == email.lower():
            return c
    return None


def search_contacts(query=""):
    contacts = _load()
    if not query:
        return contacts
    q = query.lower()
    results = []
    for c in contacts:
        if q in c.get("company", "").lower():
            results.append(c)
        elif q in c.get("contact_name", "").lower():
            results.append(c)
        elif q in c.get("email", "").lower():
            results.append(c)
        elif q in c.get("status", "").lower():
            results.append(c)
    return results


def get_recommended_next_action(contact):
    status = contact.get("status", "active")
    count = contact.get("follow_up_count", 0)
    name = contact.get("contact_name", "Unknown")
    if status == "active" and count == 0:
        return f"Send initial email to {name}"
    elif status == "followed_up_1":
        return f"Send Follow-Up 2 to {name} (Day 7-8 with value-add)"
    elif status == "followed_up_2":
        return f"Send Follow-Up 3 (Hail Mary) to {name} (Day 12-14)"
    elif status == "followed_up_3":
        return f"Contact ended. Try next person at {contact.get('company', 'this company')}"
    elif status == "responded":
        return f"Reply to {name}'s response within 12 hours"
    elif status == "scheduled_call":
        return f"Prepare for scheduled call with {name}"
    elif status in ("rejected", "closed"):
        return f"No further action needed for {name}"
    return "Check contact status"


def get_contacts_due_for_follow_up():
    """Return contacts whose next_follow_up_date is today or past due."""
    contacts = _load()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    due = []
    for c in contacts:
        next_date = c.get("next_follow_up_date")
        if next_date and next_date <= today and c.get("status") in (
            "active", "followed_up_1", "followed_up_2"
        ):
            due.append(c)
    return due


def log_outcome(contact_id, outcome):
    update_contact(contact_id, outcome=outcome, status="closed")
