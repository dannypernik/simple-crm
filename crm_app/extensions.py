"""Flask extension instances."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_migrate import Migrate


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
