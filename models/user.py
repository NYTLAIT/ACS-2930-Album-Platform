"""
models/user.py

The User model.

Relationships defined here (one side of each pair):
  - collections  : all Collection rows owned by this user
  - user_albums  : all UserAlbum rows (ratings + notes) for this user
  - comments     : all Comment rows posted by this user
  - comment_votes: all CommentVote rows cast by this user
  - album_moods  : all AlbumMood rows tagged by this user

Flask-Login requires: is_authenticated, is_active, is_anonymous, get_id.
UserMixin provides all four automatically.
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .database import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id            = db.Column(db.Integer,     primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False)

    # Relationships — lazy="select" is the SQLAlchemy default (loads on access)
    collections   = db.relationship("Collection",  back_populates="owner",  lazy="select")
    user_albums   = db.relationship("UserAlbum",   back_populates="user",   lazy="select")
    comments      = db.relationship("Comment",     back_populates="author", lazy="select")
    comment_votes = db.relationship("CommentVote", back_populates="voter",  lazy="select")
    album_moods   = db.relationship("AlbumMood",   back_populates="user",   lazy="select")

    # ── Password helpers ──────────────────────────────────────
    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        """Return True if the plaintext password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"