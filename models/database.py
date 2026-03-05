"""
models/database.py

Single shared SQLAlchemy instance.
Import db from here everywhere — never create a second instance.
init_db() is called once in create_app().
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Bind db to the Flask app and create all missing tables."""
    db.init_app(app)
    with app.app_context():
        db.create_all()