"""Database models for the CRM application."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


class TimestampMixin:
    """Mixin that adds created/updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Contact(db.Model, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str | None]
    company: Mapped[str | None]
    phone: Mapped[str | None]
    timezone: Mapped[str | None]
    tags: Mapped[str | None]
    notes: Mapped[str | None]
    last_contacted_at: Mapped[datetime | None]

    actions: Mapped[list[ContactAction]] = relationship(
        "ContactAction",
        back_populates="contact",
        cascade="all, delete-orphan",
        order_by="ContactAction.due_date",
    )

    email_suggestions: Mapped[list[EmailSuggestion]] = relationship(
        "EmailSuggestion", back_populates="contact", cascade="all, delete-orphan"
    )

    gmail_messages: Mapped[list[GmailMessage]] = relationship(
        "GmailMessage", back_populates="contact", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Contact {self.id} {self.name}>"

    @property
    def next_action(self) -> "ContactAction | None":
        """Return the next pending action."""

        pending = [action for action in self.actions if action.status == ActionStatus.PENDING]
        if not pending:
            return None
        return sorted(pending, key=lambda a: a.due_date or datetime.max)[0]


class ActionStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class ContactAction(db.Model, TimestampMixin):
    __tablename__ = "contact_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(db.ForeignKey("contacts.id"), index=True)
    title: Mapped[str]
    due_date: Mapped[datetime | None]
    status: Mapped[ActionStatus] = mapped_column(
        db.Enum(ActionStatus), default=ActionStatus.PENDING, nullable=False
    )
    completed_at: Mapped[datetime | None]
    completion_notes: Mapped[str | None]

    contact: Mapped[Contact] = relationship("Contact", back_populates="actions")
    email_suggestions: Mapped[list[EmailSuggestion]] = relationship(
        "EmailSuggestion", back_populates="action", cascade="all"
    )

    def mark_complete(self, notes: str | None = None) -> None:
        self.status = ActionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.completion_notes = notes


class SuggestionStatus(enum.StrEnum):
    CREATED = "created"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    SENT = "sent"
    NEEDS_REVIEW = "needs_review"


class EmailSuggestion(db.Model, TimestampMixin):
    __tablename__ = "email_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(db.ForeignKey("contacts.id"), index=True)
    action_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("contact_actions.id"), nullable=True
    )
    suggested_subject: Mapped[str | None]
    suggested_body: Mapped[str | None]
    suggested_send_at: Mapped[datetime | None]
    status: Mapped[SuggestionStatus] = mapped_column(
        db.Enum(SuggestionStatus), default=SuggestionStatus.CREATED, nullable=False
    )
    scheduled_for: Mapped[datetime | None]
    approved_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
    external_message_id: Mapped[str | None]
    rationale: Mapped[str | None]
    metadata: Mapped[dict | None] = mapped_column(db.JSON)

    contact: Mapped[Contact] = relationship("Contact", back_populates="email_suggestions")
    action: Mapped[ContactAction | None] = relationship("ContactAction", back_populates="email_suggestions")


class GmailCredential(db.Model, TimestampMixin):
    __tablename__ = "gmail_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str | None]
    token: Mapped[str | None]
    refresh_token: Mapped[str | None]
    token_uri: Mapped[str | None]
    client_id: Mapped[str | None]
    client_secret: Mapped[str | None]
    scopes: Mapped[str | None]
    expiry: Mapped[datetime | None]


class GmailMessageDirection(enum.StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class GmailMessage(db.Model, TimestampMixin):
    __tablename__ = "gmail_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(db.ForeignKey("contacts.id"))
    message_id: Mapped[str]
    thread_id: Mapped[str | None]
    subject: Mapped[str | None]
    snippet: Mapped[str | None]
    received_at: Mapped[datetime | None]
    direction: Mapped[GmailMessageDirection] = mapped_column(
        db.Enum(GmailMessageDirection), nullable=False
    )
    raw_payload_path: Mapped[str | None]

    contact: Mapped[Contact | None] = relationship("Contact", back_populates="gmail_messages")


class ScheduledEmail(db.Model, TimestampMixin):
    __tablename__ = "scheduled_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(db.ForeignKey("contacts.id"))
    suggestion_id: Mapped[int | None] = mapped_column(
        db.ForeignKey("email_suggestions.id")
    )
    scheduled_for: Mapped[datetime]
    status: Mapped[str] = mapped_column(default="pending")
    gmail_message_id: Mapped[str | None]
    error_message: Mapped[str | None]

    contact: Mapped[Contact] = relationship("Contact")
    suggestion: Mapped[EmailSuggestion | None] = relationship("EmailSuggestion")


@event.listens_for(Contact, "before_update")
def update_timestamp(mapper, connection, target):  # pragma: no cover - SQLAlchemy hook
    target.updated_at = datetime.utcnow()
