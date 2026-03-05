# models/user.py
# The User model stores each person's account information.
# Passwords are never stored as plain text — only as a hash.

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .database import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(25),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Relationships ---
    # A user can have many collections (playlists)
    collections = db.relationship(
        'Playlist',
        backref='owner',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # A user can rate many albums (through UserAlbum)
    user_albums = db.relationship(
        'UserAlbum',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # A user can post many comments
    comments = db.relationship(
        'Comment',
        backref='author',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # A user can vote on many comments
    comment_votes = db.relationship(
        'CommentVote',
        backref='voter',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # A user can apply mood tags to albums
    album_moods = db.relationship(
        'AlbumMood',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def set_password(self, password):
        """Hash and store the password. Never store plain text."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """Return True if the password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'