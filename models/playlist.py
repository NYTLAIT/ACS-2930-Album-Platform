from datetime import datetime
from .database import db

# Association table for many-to-many relationship between Playlist and Album
playlist_albums = db.Table(
    'playlist_albums',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('albums.id'), primary_key=True)
)

# New table to store ratings for each album by user
album_ratings = db.Table(
    'album_ratings',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('album_id', db.Integer, db.ForeignKey('albums.id'), primary_key=True),
    db.Column('rating', db.Float)  # Rating 0.5–5.0
)

class Playlist(db.Model):
    __tablename__ = 'playlists'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<Playlist {self.name}>'