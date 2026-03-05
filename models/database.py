# models/database.py
# This file creates the database object (db) and the init_db function.
# db is the SQLAlchemy instance that all models use.
# init_db connects the database to the Flask app.

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    """Connect the database to the Flask app."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
