"""Contact management routes."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...forms import ActionForm, CSVUploadForm, ContactForm
from ...models import Contact, ContactAction


bp = Blueprint("contacts", __name__)


@bp.route("/new", methods=["GET", "POST"])
def create_contact():
    contact_form = ContactForm()
    action_form = ActionForm()

    if contact_form.validate_on_submit() and action_form.validate():
        contact = Contact(
            name=contact_form.name.data,
            email=contact_form.email.data,
            company=contact_form.company.data,
            phone=contact_form.phone.data,
            timezone=contact_form.timezone.data,
            tags=contact_form.tags.data,
            notes=contact_form.notes.data,
        )
        db.session.add(contact)
        db.session.flush()

        create_action_from_form(contact, action_form)

        db.session.commit()
        flash("Contact created", "success")
        return redirect(url_for("main.dashboard"))

    return render_template(
        "contacts/new.html",
        contact_form=contact_form,
        action_form=action_form,
    )


@bp.route("/<int:contact_id>", methods=["GET"])
def view_contact(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    return render_template("contacts/detail.html", contact=contact)


@bp.route("/<int:contact_id>/edit", methods=["GET", "POST"])
def edit_contact(contact_id: int):
    contact = Contact.query.get_or_404(contact_id)
    form = ContactForm(obj=contact)

    if form.validate_on_submit():
        form.populate_obj(contact)
        db.session.commit()
        flash("Contact updated", "success")
        return redirect(url_for("contacts.view_contact", contact_id=contact.id))

    return render_template("contacts/edit.html", form=form, contact=contact)


@bp.route("/upload", methods=["GET", "POST"])
def upload_contacts():
    form = CSVUploadForm()

    if form.validate_on_submit():
        file_storage = form.file.data
        content = file_storage.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))

        imported = 0
        for row in reader:
            name = row.get("name") or row.get("Name")
            if not name:
                continue

            contact = Contact(
                name=name,
                email=row.get("email") or row.get("Email"),
                company=row.get("company") or row.get("Company"),
                phone=row.get("phone") or row.get("Phone"),
                notes=row.get("notes") or row.get("Notes"),
                tags=row.get("tags") or row.get("Tags"),
            )

            db.session.add(contact)
            db.session.flush()

            action_title = row.get("next_action") or row.get("Next Action")
            due_date_str = row.get("due_date") or row.get("Due Date")
            if action_title:
                due_date = parse_due_date(due_date_str)
                action = ContactAction(
                    contact_id=contact.id,
                    title=action_title,
                    due_date=due_date,
                )
                db.session.add(action)

            imported += 1

        db.session.commit()
        flash(f"Imported {imported} contacts", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("contacts/upload.html", form=form)


def create_action_from_form(contact: Contact, form: ActionForm) -> ContactAction | None:
    if not form.title.data:
        return None

    due_date = form.due_date.data
    if isinstance(due_date, datetime):
        due = due_date
    elif due_date:
        due = datetime.combine(due_date, datetime.min.time())
    else:
        due = None

    action = ContactAction(contact_id=contact.id, title=form.title.data, due_date=due)
    db.session.add(action)
    return action


def parse_due_date(value: str | None) -> datetime | None:
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
