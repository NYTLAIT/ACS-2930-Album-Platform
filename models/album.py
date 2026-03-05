"""
models/album.py

One Album row represents one unique Spotify album shared across all users.
Albums are created the first time any user adds them to a collection.

tracklist is stored as a JSON string because SQLite does not have a native
JSON column type. Parse it with json.loads() when you need the list.

Relationships defined here (one side):
  - user_albums: UserAlbum rows linking users to this album
  - album_moods: AlbumMood rows (mood tags applied to this album)
  - comments   : Comment rows posted on this album
  - collections: Collection rows that include this album (via join table,
                 defined on the Collection side)
"""
from .database import db


class Album(db.Model):
    __tablename__ = "albums"

    id           = db.Column(db.Integer,     primary_key=True)
    spotify_id   = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name         = db.Column(db.String(255), nullable=False)
    artist       = db.Column(db.String(255), nullable=False)
    artist_id    = db.Column(db.String(100), nullable=True)   # Spotify artist ID
    release_date = db.Column(db.String(20),  nullable=True)
    image_url    = db.Column(db.String(500), nullable=True)
    spotify_url  = db.Column(db.String(500), nullable=True)
    tracklist    = db.Column(db.Text,        nullable=True)   # JSON string
    duration_ms  = db.Column(db.Integer,     nullable=True)   # total album ms
    total_tracks = db.Column(db.Integer,     nullable=True)

    # Relationships
    user_albums  = db.relationship("UserAlbum", back_populates="album", lazy="select")
    album_moods  = db.relationship("AlbumMood",  back_populates="album", lazy="select")
    comments     = db.relationship("Comment",    back_populates="album", lazy="select",
                                   order_by="Comment.created_at")

    def __repr__(self) -> str:
        return f"<Album id={self.id} name={self.name!r} artist={self.artist!r}>"
