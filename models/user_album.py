"""
models/user_album.py

UserAlbum is the join between a User and an Album that carries data:
  - rating        : 1 (like) or -1 (dislike) or None (not rated)
  - notes         : private text only visible to the owner
  - last_viewed_at: stamped every time the user visits the album detail page
                    used by the dashboard recent activity section

One user can only have one UserAlbum per album (UniqueConstraint).

RATING_LIKE and RATING_DISLIKE are the only valid non-null rating values.
"""
from datetime import datetime
from .database import db

RATING_LIKE    =  1
RATING_DISLIKE = -1


class UserAlbum(db.Model):
    __tablename__ = "user_albums"

    id             = db.Column(db.Integer,  primary_key=True)
    user_id        = db.Column(db.Integer,  db.ForeignKey("users.id",  ondelete="CASCADE"),
                               nullable=False, index=True)
    album_id       = db.Column(db.Integer,  db.ForeignKey("albums.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    rating         = db.Column(db.Integer,  nullable=True)   # 1, -1, or None
    notes          = db.Column(db.Text,     nullable=True)   # private to this user
    created_at     = db.Column(db.DateTime, default=datetime.utcnow,  nullable=False)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow, nullable=False)
    last_viewed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "album_id", name="uq_user_album"),
    )

    # Relationships
    user  = db.relationship("User",  back_populates="user_albums")
    album = db.relationship("Album", back_populates="user_albums")

    def __repr__(self) -> str:
        return f"<UserAlbum user={self.user_id} album={self.album_id} rating={self.rating}>"