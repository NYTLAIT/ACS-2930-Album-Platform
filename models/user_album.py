#  -1  = Dislike
#   None = not yet rated
#
# To change to a 5-star system later, just change the rating column
# to allow values 1–5 and update the UI. Nothing else needs to change.

from datetime import datetime
from .database import db

# These are the only valid rating values.
# Changing this is the only thing you need to do to update the rating system.
RATING_LIKE    =  1
RATING_DISLIKE = -1


class UserAlbum(db.Model):
    __tablename__ = 'user_albums'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),  nullable=False)
    album_id   = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=False)

    # Rating: 1 = Like, -1 = Dislike, None = not rated yet
    rating     = db.Column(db.Integer, nullable=True)

    # Personal note — only visible to this user
    notes      = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Make sure one user can only have one entry per album
    __table_args__ = (
        db.UniqueConstraint('user_id', 'album_id', name='unique_user_album'),
    )

    def __repr__(self):
        return f'<UserAlbum user={self.user_id} album={self.album_id} rating={self.rating}>'