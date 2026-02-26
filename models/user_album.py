from .database import db
from .user import User
from .album import Album

class UserAlbum(db.Model):
    __tablename__ = 'user_albums'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=False)
    rating = db.Column(db.Float)  # 0.5 - 5.0
    notes = db.Column(db.Text)

    # Relationships
    user = db.relationship('User', backref=db.backref('user_albums', cascade='all, delete-orphan'))
    album = db.relationship('Album', backref=db.backref('user_albums', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserAlbum {self.user.username} - {self.album.name} ({self.rating})>'