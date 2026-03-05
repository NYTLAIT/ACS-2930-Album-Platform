# models/album.py
# The Album model stores albums retrieved from the Spotify API.
# Albums are shared across all users — if two users add the same
# album, only one row exists here. The per-user data (rating, notes,
# moods) lives in UserAlbum and AlbumMood.

from .database import db


class Album(db.Model):
    __tablename__ = 'albums'

    id           = db.Column(db.Integer,     primary_key=True)
    spotify_id   = db.Column(db.String(50),  unique=True, nullable=False)
    name         = db.Column(db.String(255), nullable=False)
    artist       = db.Column(db.String(255), nullable=False)
    artist_id    = db.Column(db.String(50))   # Spotify artist ID, used for artist page
    release_date = db.Column(db.String(10))   # Format: YYYY-MM-DD
    image_url    = db.Column(db.String(500))
    spotify_url  = db.Column(db.String(500))

    # Track data stored as plain text (JSON string).
    # Format: '[{"name": "Track 1", "duration_ms": 210000}, ...]'
    # We store it as a string to keep the model simple.
    # In templates, use the `|fromjson` filter or parse in the route.
    tracklist    = db.Column(db.Text)

    # Total album duration in milliseconds (from Spotify)
    duration_ms  = db.Column(db.Integer)

    # Total number of tracks
    total_tracks = db.Column(db.Integer)

    # --- Relationships ---
    # All per-user rating/notes entries for this album
    user_albums = db.relationship(
        'UserAlbum',
        backref='album',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # All mood tags applied to this album by any user
    album_moods = db.relationship(
        'AlbumMood',
        backref='album',
        lazy=True,
        cascade='all, delete-orphan'
    )

    # All comments on this album
    comments = db.relationship(
        'Comment',
        backref='album',
        lazy=True,
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Album {self.name} by {self.artist}>'
