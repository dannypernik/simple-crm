"""Utilities for Gmail OAuth and message syncing."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Iterable

from flask import current_app, url_for
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow

from ..extensions import db
from ..models import Contact, GmailCredential, GmailMessage, GmailMessageDirection


def get_flow(state: str | None = None) -> Flow:
    """Create an OAuth flow using configured credentials."""

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = current_app.config.get("GOOGLE_REDIRECT_URI") or url_for(
        "gmail.oauth_callback", _external=True
    )

    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth environment variables not configured")

    return Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=current_app.config["GOOGLE_SCOPES"].split(),
        redirect_uri=redirect_uri,
        state=state,
    )


def save_credentials(credentials: Credentials) -> GmailCredential:
    """Persist credentials to the database."""

    record = GmailCredential.query.first()
    if record is None:
        record = GmailCredential()

    record.user_email = credentials.id_token.get("email") if credentials.id_token else None
    record.token = credentials.token
    record.refresh_token = credentials.refresh_token
    record.token_uri = credentials.token_uri
    record.client_id = credentials.client_id
    record.client_secret = credentials.client_secret
    record.scopes = " ".join(credentials.scopes or [])
    record.expiry = credentials.expiry

    db.session.add(record)
    db.session.commit()

    return record


def load_credentials() -> Credentials | None:
    record = GmailCredential.query.first()
    if not record or not record.token:
        return None

    return Credentials(
        token=record.token,
        refresh_token=record.refresh_token,
        token_uri=record.token_uri,
        client_id=record.client_id,
        client_secret=record.client_secret,
        scopes=record.scopes.split() if record.scopes else None,
        expiry=record.expiry,
    )


def build_service(credentials: Credentials | None = None):
    credentials = credentials or load_credentials()
    if not credentials:
        raise RuntimeError("No Gmail credentials available")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def sync_recent_messages(limit: int = 20) -> list[GmailMessage]:
    """Fetch the most recent messages and store them."""

    service = build_service()
    try:
        response = (
            service.users()
            .messages()
            .list(userId="me", maxResults=limit, labelIds=["INBOX"])
            .execute()
        )
    except HttpError as exc:  # pragma: no cover - network failure
        current_app.logger.error("Failed to list Gmail messages", exc_info=exc)
        raise

    messages = response.get("messages", [])
    stored_messages: list[GmailMessage] = []
    contacts_to_refresh = set()
    for metadata in messages:
        msg_id = metadata["id"]
        if GmailMessage.query.filter_by(message_id=msg_id).first():
            continue

        message_resource = (
            service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        )

        parsed = parse_message(message_resource)
        if not parsed:
            continue

        gmail_message = GmailMessage(**parsed)
        db.session.add(gmail_message)
        stored_messages.append(gmail_message)
        if gmail_message.direction == GmailMessageDirection.INCOMING and gmail_message.contact_id:
            contacts_to_refresh.add(gmail_message.contact_id)

    db.session.commit()

    if contacts_to_refresh:
        from . import suggestions as suggestion_service

        for contact_id in contacts_to_refresh:
            contact = Contact.query.get(contact_id)
            if contact:
                suggestion_service.mark_suggestions_needing_review(contact)

    return stored_messages


def parse_message(payload: dict | None) -> dict | None:
    if not payload:
        return None

    headers = {header["name"].lower(): header["value"] for header in payload.get("payload", {}).get("headers", [])}
    subject = headers.get("subject")
    from_email = headers.get("from", "")
    to_email = headers.get("to", "")
    received_at = payload.get("internalDate")

    contact = match_contact(from_email, to_email)

    snippet = payload.get("snippet")
    body = extract_body(payload.get("payload", {}))

    direction = GmailMessageDirection.INCOMING if contact and contact.email and contact.email in from_email else GmailMessageDirection.OUTGOING

    received_dt = datetime.fromtimestamp(int(received_at) / 1000, tz=timezone.utc) if received_at else None

    return {
        "contact_id": contact.id if contact else None,
        "message_id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "subject": subject,
        "snippet": snippet or (body[:120] if body else None),
        "received_at": received_dt,
        "direction": direction,
    }


def match_contact(from_email: str, to_email: str) -> Contact | None:
    email_candidates = set()
    if "<" in from_email and ">" in from_email:
        email_candidates.add(from_email.split("<")[-1].split(">")[0])
    else:
        email_candidates.add(from_email)

    if "<" in to_email and ">" in to_email:
        email_candidates.add(to_email.split("<")[-1].split(">")[0])
    else:
        email_candidates.add(to_email)

    for email in email_candidates:
        candidate = Contact.query.filter(Contact.email.ilike(email.strip())).first()
        if candidate:
            return candidate
    return None


def extract_body(part: dict | None) -> str:
    if not part:
        return ""

    body = part.get("body")
    data = (body or {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data.encode()).decode(errors="ignore")

    for sub_part in part.get("parts", []):
        text = extract_body(sub_part)
        if text:
            return text
    return ""


def messages_for_contact(contact: Contact) -> Iterable[GmailMessage]:
    return GmailMessage.query.filter_by(contact_id=contact.id).order_by(GmailMessage.received_at.desc())


def send_email(contact: Contact, subject: str, body: str) -> str:
    """Send an email via the Gmail API and log it."""

    credentials = load_credentials()
    if not credentials:
        raise RuntimeError("Gmail credentials are required to send email")

    service = build_service(credentials)

    from email.message import EmailMessage

    message = EmailMessage()
    sender_email = credentials.id_token.get("email") if credentials.id_token else "me"
    message["To"] = contact.email
    message["From"] = sender_email
    message["Subject"] = subject
    message.set_content(body)

    encoded_message = {
        "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
    }

    response = (
        service.users()
        .messages()
        .send(userId="me", body=encoded_message)
        .execute()
    )

    gmail_message = GmailMessage(
        contact_id=contact.id,
        message_id=response.get("id"),
        thread_id=response.get("threadId"),
        subject=subject,
        snippet=body[:120],
        received_at=datetime.utcnow(),
        direction=GmailMessageDirection.OUTGOING,
    )
    db.session.add(gmail_message)
    contact.last_contacted_at = datetime.utcnow()
    db.session.commit()

    return response.get("id")
