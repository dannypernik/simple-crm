"""Blueprint for managing email suggestions and scheduling."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...forms import EmailSuggestionApprovalForm
from ...models import Contact, EmailSuggestion, ScheduledEmail, SuggestionStatus
from ...services import scheduler as scheduler_service
from ...services import suggestions as suggestion_service


bp = Blueprint("emails", __name__)


@bp.route("/suggestions", methods=["GET", "POST"])
def suggestion_inbox():
    suggestions = (
        EmailSuggestion.query.order_by(EmailSuggestion.created_at.desc())
        .limit(50)
        .all()
    )

    forms = {
        suggestion.id: EmailSuggestionApprovalForm(
            prefix=str(suggestion.id),
            data={
                "suggestion_id": suggestion.id,
                "subject": suggestion.suggested_subject,
                "body": suggestion.suggested_body,
                "suggested_send_at": suggestion.suggested_send_at,
                "status": suggestion.status.value
                if suggestion.status in {SuggestionStatus.APPROVED, SuggestionStatus.SCHEDULED}
                else SuggestionStatus.APPROVED.value,
            },
        )
        for suggestion in suggestions
    }

    if request.method == "POST":
        suggestion_id = request.form.get("suggestion_id")
        if not suggestion_id:
            flash("Missing suggestion", "warning")
            return redirect(url_for("emails.suggestion_inbox"))

        suggestion = EmailSuggestion.query.get(int(suggestion_id))
        if not suggestion:
            flash("Suggestion not found", "danger")
            return redirect(url_for("emails.suggestion_inbox"))

        form = EmailSuggestionApprovalForm(prefix=str(suggestion.id))
        if form.validate_on_submit():
            suggestion.suggested_subject = form.subject.data
            suggestion.suggested_body = form.body.data
            suggestion.suggested_send_at = form.suggested_send_at.data
            desired_status = SuggestionStatus(form.status.data)

            if desired_status == SuggestionStatus.APPROVED:
                send_at = form.suggested_send_at.data or datetime.utcnow()
                suggestion.status = SuggestionStatus.APPROVED
                suggestion.approved_at = datetime.utcnow()
                scheduled = ScheduledEmail.query.filter_by(suggestion_id=suggestion.id).first()
                if scheduled:
                    scheduler_service.scheduler.remove_job(f"scheduled-email-{scheduled.id}")
                    db.session.delete(scheduled)
                    db.session.flush()
                scheduler_service.schedule_email(suggestion, send_at)
                flash("Email scheduled", "success")
            else:
                suggestion.status = SuggestionStatus.NEEDS_REVIEW
                suggestion.approved_at = None
                suggestion.scheduled_for = None
                db.session.commit()

            return redirect(url_for("emails.suggestion_inbox"))

        flash("Please correct the errors in the form", "danger")

    return render_template("emails/suggestions.html", suggestions=suggestions, forms=forms)


@bp.route("/suggestions/generate/<int:contact_id>", methods=["POST"])
def generate_suggestion(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    action = contact.next_action
    suggestion_service.generate_for_contact(contact, action)
    flash("Generated suggestion", "success")
    return redirect(url_for("emails.suggestion_inbox"))


@bp.route("/suggestions/refresh/<int:suggestion_id>", methods=["POST"])
def refresh_suggestion(suggestion_id: int):
    suggestion = EmailSuggestion.query.get_or_404(suggestion_id)
    contact = suggestion.contact
    action = suggestion.action or contact.next_action
    suggestion_service.generate_for_contact(contact, action)

    # Remove old suggestion from scheduling
    scheduled_records = ScheduledEmail.query.filter_by(suggestion_id=suggestion.id).all()
    for record in scheduled_records:
        try:  # pragma: no cover - scheduler removal
            scheduler_service.scheduler.remove_job(f"scheduled-email-{record.id}")
        except Exception:
            pass
        db.session.delete(record)
    db.session.delete(suggestion)
    db.session.commit()

    flash("Suggestion refreshed", "info")
    return redirect(url_for("emails.suggestion_inbox"))
