from datetime import datetime
from .database import db

class AlbumComment(db.Model):
    __tablename__ = 'album_comments'

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('album_comments.id'))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    album = db.relationship('Album', backref=db.backref('comments', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('album_comments', cascade='all, delete-orphan'))
    parent = db.relationship('AlbumComment', remote_side=[id], backref=db.backref('replies', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<AlbumComment {self.id} on album {self.album_id}>'


class CommentVote(db.Model):
    __tablename__ = 'comment_votes'

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('album_comments.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # +1 for upvote, -1 for downvote

    # Relationships
    comment = db.relationship('AlbumComment', backref=db.backref('votes', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('comment_votes', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<CommentVote {self.value} by user {self.user_id} on comment {self.comment_id}>'
