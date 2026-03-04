from datetime import datetime
from .database import db


class Album(db.Model):
    __tablename__ = 'albums'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)

    # Keep plain-text artist for backwards compatibility, but
    # prefer using the Artist relationship where possible.
    artist = db.Column(db.String(255), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artists.id'))

    release_date = db.Column(db.String(10))  # Format: YYYY-MM-DD
    image_url = db.Column(db.String(500))
    spotify_url = db.Column(db.String(500))

    # Optional extended metadata
    description = db.Column(db.Text)
    genres = db.Column(db.String(500))  # Comma-separated list from Spotify

    # Relationships
    playlists = db.relationship('Playlist', secondary='playlist_albums', backref='albums')
    artist_obj = db.relationship('Artist', backref='albums')

    def __repr__(self):
        return f'<Album {self.name} by {self.artist}>'
