import os
import json
import base64
import mimetypes
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SENDER_EMAIL = "dhruvg096@gmail.com"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_FILE = "gmail_token.json"


def authenticate(creds_dict_or_path):
    """Authenticate with Gmail API using OAuth2 credentials.

    Args:
        creds_dict_or_path: Dict with parsed credentials JSON, or path to file.

    Returns:
        Google API service object.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
        except Exception:
            creds = None
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if isinstance(creds_dict_or_path, dict):
            client_config = creds_dict_or_path
        else:
            with open(creds_dict_or_path, "r") as f:
                client_config = json.load(f)
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    service = build("gmail", "v1", credentials=creds)
    return service


def create_message(to, subject, body, attachment_path=None):
    """Create a base64url-encoded RFC 2822 compliant message.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
        attachment_path: Optional path to a file to attach.

    Returns:
        Dict with 'raw' key containing the base64url-encoded message.
    """
    msg = EmailMessage()
    msg.set_content(body)
    msg["To"] = to
    msg["From"] = SENDER_EMAIL
    msg["Subject"] = subject

    if attachment_path and os.path.exists(attachment_path):
        type_subtype, _ = mimetypes.guess_type(attachment_path)
        if type_subtype is None:
            maintype, subtype = "application", "octet-stream"
        else:
            maintype, subtype = type_subtype.split("/", 1)
        with open(attachment_path, "rb") as fp:
            attachment_data = fp.read()
        msg.add_attachment(attachment_data, maintype, subtype)
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                part.replace_header('Content-Disposition', 'attachment; filename="DhruvGoyal_res.pdf"')
                break

    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": encoded}


def send_message(service, to, subject, body, attachment_path=None):
    """Send an email via Gmail API.

    Args:
        service: Authenticated Gmail API service object.
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
        attachment_path: Optional path to a file to attach.

    Returns:
        Dict with 'success' and 'message_id' keys.

    Raises:
        RuntimeError: On Gmail API error.
    """
    message = create_message(to, subject, body, attachment_path)
    try:
        sent = (
            service.users()
            .messages()
            .send(userId="me", body=message)
            .execute()
        )
        return {"success": True, "message_id": sent.get("id")}
    except HttpError as e:
        raise RuntimeError(f"Gmail API error: {e}")


def test_connection(creds_dict_or_path):
    """Test Gmail API credentials by authenticating and making a lightweight call."""
    try:
        service = authenticate(creds_dict_or_path)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "")
        return {"success": True, "email": email}
    except Exception as e:
        return {"success": False, "error": str(e)}
