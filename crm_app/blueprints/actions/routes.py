"""Action-related routes."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...forms import ActionCompleteForm, ActionForm
from ...models import ActionStatus, Contact, ContactAction


bp = Blueprint("actions", __name__)


@bp.route("/new/<int:contact_id>", methods=["GET", "POST"])
def add_action(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    form = ActionForm()

    if form.validate_on_submit():
        due_date = form.due_date.data
        if due_date:
            due_datetime = datetime.combine(due_date, datetime.min.time())
        else:
            due_datetime = None

        action = ContactAction(
            contact_id=contact.id,
            title=form.title.data,
            due_date=due_datetime,
        )
        db.session.add(action)
        db.session.commit()
        flash("Action added", "success")
        return redirect(url_for("contacts.view_contact", contact_id=contact.id))

    return render_template("actions/new.html", form=form, contact=contact)


@bp.route("/<int:action_id>/complete", methods=["GET", "POST"])
def complete_action(action_id: int):
    action = ContactAction.query.get_or_404(action_id)
    if action.status == ActionStatus.COMPLETED:
        flash("Action already completed", "info")
        return redirect(url_for("main.dashboard"))

    form = ActionCompleteForm()

    if form.validate_on_submit():
        action.mark_complete(notes=form.completion_notes.data)

        # Create next action
        new_due_date = form.new_due_date.data
        if new_due_date:
            due_datetime = datetime.combine(new_due_date, datetime.min.time())
        else:
            due_datetime = None

        next_action = ContactAction(
            contact_id=action.contact_id,
            title=form.new_title.data,
            due_date=due_datetime,
        )
        db.session.add(next_action)
        db.session.commit()

        flash("Action completed and next action scheduled", "success")
        return redirect(url_for("main.dashboard"))

    if request.method == "GET":
        form.new_title.data = action.title

    return render_template("actions/complete.html", form=form, action=action)
