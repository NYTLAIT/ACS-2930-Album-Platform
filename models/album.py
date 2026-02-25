from datetime import datetime
from .database import db

class Album(db.Model):
    __tablename__ = 'albums'
    
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=False)
    release_date = db.Column(db.String(10))  # Format: YYYY-MM-DD
    image_url = db.Column(db.String(500))
    spotify_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    playlists = db.relationship('Playlist', secondary='playlist_albums', backref='albums')
    
    def __repr__(self):
        return f'<Album {self.name} by {self.artist}>'
