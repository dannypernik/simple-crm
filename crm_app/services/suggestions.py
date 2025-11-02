"""AI-assisted email suggestion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from flask import current_app

from ..extensions import db
from ..models import Contact, ContactAction, EmailSuggestion, ScheduledEmail, SuggestionStatus
from . import scheduler as scheduler_service
from . import gmail as gmail_service


try:  # pragma: no cover - optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback if OpenAI not installed
    OpenAI = None  # type: ignore


@dataclass
class SuggestionResult:
    subject: str
    body: str
    send_at: datetime
    rationale: str


FALLBACK_TEMPLATE = """
Hi {name},

I hope you're doing well. I wanted to follow up regarding {action}.

Best,
{sender}
""".strip()


def generate_for_contact(contact: Contact, action: ContactAction | None = None) -> EmailSuggestion:
    """Generate or refresh an email suggestion for a contact."""

    messages = list(gmail_service.messages_for_contact(contact))
    result = call_model(contact, action, messages)

    suggestion = EmailSuggestion(
        contact_id=contact.id,
        action_id=action.id if action else None,
        suggested_subject=result.subject,
        suggested_body=result.body,
        suggested_send_at=result.send_at,
        rationale=result.rationale,
    )

    db.session.add(suggestion)
    db.session.commit()

    return suggestion


def call_model(
    contact: Contact,
    action: ContactAction | None,
    messages: Sequence,
) -> SuggestionResult:
    """Call OpenAI (or fallback) to create a suggestion."""

    api_key = current_app.config.get("OPENAI_API_KEY")
    sender_name = current_app.config.get("SENDER_NAME", "Your Name")

    if api_key and OpenAI:
        client = OpenAI(api_key=api_key)
        prompt = build_prompt(contact, action, messages, sender_name)
        completion = client.responses.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            input=prompt,
        )
        output = completion.output_text or ""
        subject, body, rationale = parse_model_output(output)
    else:
        subject, body, rationale = fallback_suggestion(contact, action, sender_name)

    due_date = action.due_date if action and action.due_date else datetime.utcnow() + timedelta(days=2)

    return SuggestionResult(
        subject=subject,
        body=body,
        send_at=due_date,
        rationale=rationale,
    )


def build_prompt(contact: Contact, action: ContactAction | None, messages, sender_name: str) -> str:
    history_snippets = []
    for message in list(messages)[:5]:
        direction = "From contact" if message.direction.value == "incoming" else "From you"
        snippet = message.snippet or "(no snippet)"
        history_snippets.append(f"- {direction}: {snippet}")

    history_text = "\n".join(history_snippets) if history_snippets else "No prior messages available."
    action_text = action.title if action else "follow up"

    return (
        "You are an assistant helping craft concise follow-up emails for a CRM."\
        "\n" "Contact name: {contact.name}"\
        "\n" "Company: {contact.company}"\
        "\n" "Pending action: {action_text}"\
        "\n" "History:\n{history}"\
        "\n" "Write a subject line and a short body."\
        "\n" "Respond in the format: Subject: <subject line>\nBody:\n<body>\nRationale: <one sentence>."\
        ).format(contact=contact, action_text=action_text, history=history_text)


def parse_model_output(output: str) -> tuple[str, str, str]:
    subject = "Follow up"
    rationale = "Suggested by heuristic"
    body_lines: list[str] = []

    for line in output.splitlines():
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip() or subject
        elif line.lower().startswith("rationale:"):
            rationale = line.split(":", 1)[1].strip() or rationale
        else:
            body_lines.append(line)

    body = "\n".join(l for l in body_lines if l.strip())
    if not body:
        body = "Just checking in."

    return subject, body, rationale


def fallback_suggestion(contact: Contact, action: ContactAction | None, sender_name: str) -> tuple[str, str, str]:
    subject = f"Checking in about {action.title}" if action else f"Checking in with {contact.name}"
    body = FALLBACK_TEMPLATE.format(
        name=contact.name,
        action=action.title if action else "our recent conversation",
        sender=sender_name,
    )
    rationale = "Generated with fallback template"
    return subject, body, rationale


def mark_suggestions_needing_review(contact: Contact) -> None:
    for suggestion in contact.email_suggestions:
        if suggestion.status in {SuggestionStatus.APPROVED, SuggestionStatus.SCHEDULED}:
            suggestion.status = SuggestionStatus.NEEDS_REVIEW
            suggestion.scheduled_for = None
            scheduled = ScheduledEmail.query.filter_by(suggestion_id=suggestion.id).first()
            if scheduled:
                scheduled.status = "cancelled"
                try:  # pragma: no cover - scheduler removal
                    scheduler_service.scheduler.remove_job(f"scheduled-email-{scheduled.id}")
                except Exception:
                    pass
    db.session.commit()
