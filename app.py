"""Entry point for running the CRM Flask app."""

from crm_app import create_app


app = create_app()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    app.run()
