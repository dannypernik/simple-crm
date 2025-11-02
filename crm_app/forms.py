"""Form classes used throughout the CRM application."""

from __future__ import annotations

from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import DateField, DateTimeField, FileField, HiddenField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional

from .models import SuggestionStatus


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[Optional(), Email()])
    company = StringField("Company", validators=[Optional()])
    phone = StringField("Phone", validators=[Optional()])
    timezone = StringField("Time Zone", validators=[Optional()])
    tags = StringField("Tags", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])


class ActionForm(FlaskForm):
    title = StringField("Next Action", validators=[DataRequired()])
    due_date = DateField("Due Date", validators=[Optional()])


class ActionCompleteForm(FlaskForm):
    completion_notes = TextAreaField("Completion Notes", validators=[Optional()])
    new_title = StringField("Next Action", validators=[DataRequired()])
    new_due_date = DateField("Next Due Date", validators=[Optional()])


class CSVUploadForm(FlaskForm):
    file = FileField("CSV File", validators=[DataRequired()])


class EmailSuggestionApprovalForm(FlaskForm):
    suggestion_id = HiddenField(validators=[DataRequired()])
    subject = StringField("Subject", validators=[DataRequired()])
    body = TextAreaField("Body", validators=[DataRequired()])
    suggested_send_at = DateTimeField(
        "Send At",
        validators=[Optional()],
        default=lambda: datetime.utcnow(),
        format="%Y-%m-%dT%H:%M",
        render_kw={"type": "datetime-local"},
    )
    status = SelectField(
        "Status",
        choices=[
            (SuggestionStatus.APPROVED.value, "Approve"),
            (SuggestionStatus.NEEDS_REVIEW.value, "Needs Review"),
        ],
        validators=[DataRequired()],
    )
