"""Blueprint handling Gmail OAuth connection and sync."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from ...extensions import db
from ...models import GmailCredential
from ...services import gmail as gmail_service


bp = Blueprint("gmail", __name__)


@bp.route("/connect")
def connect():
    """Initiate the Google OAuth flow."""

    try:
        flow = gmail_service.get_flow()
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("main.dashboard"))

    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["google_oauth_state"] = state
    return redirect(authorization_url)


@bp.route("/oauth2callback")
def oauth_callback():
    state = session.pop("google_oauth_state", None)
    if not state:
        flash("Invalid OAuth state", "danger")
        return redirect(url_for("main.dashboard"))

    flow = gmail_service.get_flow(state)
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    gmail_service.save_credentials(credentials)
    flash("Gmail account connected", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/disconnect", methods=["POST"])
def disconnect():
    record = GmailCredential.query.first()
    if record:
        db.session.delete(record)
        db.session.commit()
        flash("Disconnected Gmail account", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/sync", methods=["POST"])
def sync():
    try:
        stored = gmail_service.sync_recent_messages()
        flash(f"Synced {len(stored)} messages", "success")
    except RuntimeError as exc:
        flash(str(exc), "warning")
    return redirect(url_for("main.dashboard"))
