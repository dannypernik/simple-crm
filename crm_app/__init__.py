"""Application factory for the CRM Flask app."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask

from .config import get_config
from .extensions import csrf, db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """Application factory used by Flask.

    Args:
        config_name: Optional configuration name. Defaults to ``FLASK_ENV`` value
            or ``development``.
    """

    config_name = config_name or getenv_default("FLASK_ENV", "development")

    app = Flask(__name__, instance_path=str(Path.cwd() / "instance"))
    app.config.from_object(get_config(config_name))

    configure_logging(app)
    register_extensions(app)
    register_blueprints(app)
    register_context_processors(app)
    register_cli(app)

    ensure_instance_folder(app)

    return app


def getenv_default(key: str, default: str) -> str:
    """Helper to fetch environment variables with fallback."""

    import os

    return os.getenv(key, default)


def configure_logging(app: Flask) -> None:
    """Configure application logging."""

    if app.debug:
        return

    gunicorn_error_logger = logging.getLogger("gunicorn.error")
    if gunicorn_error_logger.handlers and app.logger.handlers:
        app.logger.handlers = gunicorn_error_logger.handlers
        app.logger.setLevel(gunicorn_error_logger.level)


def register_extensions(app: Flask) -> None:
    """Register Flask extensions."""

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from .services import scheduler

    scheduler.init_app(app)


def register_blueprints(app: Flask) -> None:
    """Attach Flask blueprints."""

    from .blueprints.main.routes import bp as main_bp
    from .blueprints.contacts.routes import bp as contacts_bp
    from .blueprints.actions.routes import bp as actions_bp
    from .blueprints.gmail.routes import bp as gmail_bp
    from .blueprints.emails.routes import bp as emails_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp, url_prefix="/contacts")
    app.register_blueprint(actions_bp, url_prefix="/actions")
    app.register_blueprint(gmail_bp, url_prefix="/gmail")
    app.register_blueprint(emails_bp, url_prefix="/emails")


def register_context_processors(app: Flask) -> None:
    from .models import GmailCredential

    @app.context_processor
    def inject_gmail_status() -> dict[str, object]:
        record = GmailCredential.query.first()
        return {
            "gmail_connected": bool(record and record.token),
            "gmail_account": record.user_email if record else None,
        }


def register_cli(app: Flask) -> None:
    """Register custom CLI commands."""

    from .models import Contact

    @app.shell_context_processor
    def shell_context() -> dict[str, object]:  # pragma: no cover - shell helper
        return {
            "db": db,
            "Contact": Contact,
        }


def ensure_instance_folder(app: Flask) -> None:
    """Make sure the instance folder exists for SQLite database."""

    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover - best effort
        app.logger.warning("Could not create instance folder", exc_info=True)
