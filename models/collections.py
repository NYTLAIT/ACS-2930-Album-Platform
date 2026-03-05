# New fields added:
#   description — optional text the user can write about the collection
#   is_public   — if True, other users can see this collection

from datetime import datetime
from .database import db


# Join table — connects playlists to albums (many-to-many).
# This is not a full model, just a helper table with two foreign keys.
collection_albums = db.Table(
    'collection_albums',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('album_id',    db.Integer, db.ForeignKey('albums.id'),    primary_key=True)
)


class Playlist(db.Model):
    __tablename__ = 'playlists'

    id          = db.Column(db.Integer,      primary_key=True)
    name        = db.Column(db.String(255),  nullable=False)
    description = db.Column(db.Text)                          # optional description
    is_public   = db.Column(db.Boolean,      default=False)   # private by default
    user_id     = db.Column(db.Integer,      db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    # Albums in this collection
    albums = db.relationship(
        'Album',
        secondary=collection_albums,
        backref='playlists',
        lazy=True
    )

    def __repr__(self):
        return f'<Playlist {self.name}>'
