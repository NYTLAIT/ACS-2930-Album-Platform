# models/comment.py
# Two models live here:
#
# Comment     — a comment posted by a user on an album detail page.
#               Comments can reply to other comments (threading) via parent_id.
#
# CommentVote — records one user's vote on one comment.
#               value = 1 means upvote, value = -1 means downvote.
#               A user can remove their vote by deleting this row (toggle behaviour).
#               One vote per user per comment is enforced by the unique constraint.

from datetime import datetime
from .database import db


class Comment(db.Model):
    __tablename__ = 'comments'

    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text,    nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),  nullable=False)
    album_id   = db.Column(db.Integer, db.ForeignKey('albums.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # parent_id is None for top-level comments.
    # If set, this comment is a reply to the comment with that id.
    parent_id  = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)

    # replies gives easy access to all direct replies to this comment
    replies = db.relationship(
        'Comment',
        backref=db.backref('parent', remote_side=[id]),
        lazy=True
    )

    # votes gives access to all vote rows for this comment
    votes = db.relationship(
        'CommentVote',
        backref='comment',
        lazy=True,
        cascade='all, delete-orphan'
    )

    @property
    def score(self):
        """Total score = upvotes minus downvotes."""
        return sum(v.value for v in self.votes)

    def __repr__(self):
        return f'<Comment {self.id} by user={self.user_id} on album={self.album_id}>'


class CommentVote(db.Model):
    __tablename__ = 'comment_votes'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'),    nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=False)

    # 1 = upvote, -1 = downvote
    value      = db.Column(db.Integer, nullable=False)

    # One user can only have one vote per comment
    __table_args__ = (
        db.UniqueConstraint('user_id', 'comment_id', name='unique_comment_vote'),
    )

    def __repr__(self):
        return f'<CommentVote user={self.user_id} comment={self.comment_id} value={self.value}>'
