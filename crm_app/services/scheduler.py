"""Simple APScheduler integration for sending scheduled emails."""

from __future__ import annotations

import atexit
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

from ..extensions import db
from ..models import EmailSuggestion, ScheduledEmail, SuggestionStatus
from . import gmail as gmail_service


_flask_app = None
scheduler = BackgroundScheduler(timezone="UTC")


def init_app(app):
    global _flask_app
    _flask_app = app
    if not scheduler.running:
        scheduler.start()
        atexit.register(_shutdown_scheduler)


def schedule_email(suggestion: EmailSuggestion, send_at: datetime) -> ScheduledEmail:
    record = ScheduledEmail(
        contact_id=suggestion.contact_id,
        suggestion_id=suggestion.id,
        scheduled_for=send_at,
        status="scheduled",
    )
    db.session.add(record)
    suggestion.status = SuggestionStatus.SCHEDULED
    suggestion.scheduled_for = send_at
    db.session.commit()

    scheduler.add_job(
        func=dispatch_email,
        trigger="date",
        run_date=send_at,
        args=[record.id],
        id=f"scheduled-email-{record.id}",
        replace_existing=True,
    )

    return record


def dispatch_email(scheduled_email_id: int):  # pragma: no cover - background task
    app = _flask_app
    if app is None:
        return
    with app.app_context():
        record = ScheduledEmail.query.get(scheduled_email_id)
        if not record or record.status == "sent":
            return

        suggestion = record.suggestion
        contact = suggestion.contact if suggestion else record.contact

        try:
            message_id = gmail_service.send_email(
                contact,
                suggestion.suggested_subject if suggestion else "Follow up",
                suggestion.suggested_body if suggestion else "",
            )
            record.status = "sent"
            record.gmail_message_id = message_id
            suggestion.status = SuggestionStatus.SENT
            suggestion.sent_at = datetime.utcnow()
            db.session.commit()
        except Exception as exc:  # pragma: no cover - best effort
            record.status = "error"
            record.error_message = str(exc)
            db.session.commit()


def _shutdown_scheduler():  # pragma: no cover - process shutdown helper
    if scheduler.running and not scheduler._stopped:
        scheduler.shutdown(wait=False)
