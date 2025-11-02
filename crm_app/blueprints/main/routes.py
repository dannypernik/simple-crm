"""Routes for the main dashboard view."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, render_template, request

from ...extensions import db
from ...models import ActionStatus, Contact, ContactAction


bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    """Render the dashboard showing contacts by next action due."""

    search = request.args.get("q", "").strip()

    query = Contact.query
    if search:
        ilike_search = f"%{search}%"
        query = query.filter(
            db.or_(
                Contact.name.ilike(ilike_search),
                Contact.email.ilike(ilike_search),
                Contact.company.ilike(ilike_search),
            )
        )

    contacts = query.all()

    sorted_contacts = sorted(
        contacts,
        key=lambda contact: (
            contact.next_action.due_date if contact.next_action else datetime.max,
            contact.name.lower(),
        ),
    )

    upcoming_actions = (
        ContactAction.query.filter_by(status=ActionStatus.PENDING)
        .order_by(ContactAction.due_date.asc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        contacts=sorted_contacts,
        upcoming_actions=upcoming_actions,
        search=search,
    )
