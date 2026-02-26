# Defining database for easier calls and initializing
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Importing to ecouter.py
def init_db(app):
    """
    Initialize the database with the Flask app.
    Handle both SQLAlchemy setup and table creation.
    """
    db.init_app(app) # db sqlalchemy object, let db know which flask app to connect to
    with app.app_context():
        db.create_all()