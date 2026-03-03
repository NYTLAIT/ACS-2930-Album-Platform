from .database import db

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Float)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=db.func.now())

    user = db.relationship('User', backref='reviews')
    album = db.relationship('Album', backref='reviews')

    def __repr__(self):
        return f'<Review {self.rating} by {self.user.username} for {self.album.name}>'