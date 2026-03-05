"""
models/comment.py

Comment supports threading via the self-referential parent_id foreign key.
  - parent_id = None  → top-level comment
  - parent_id = int   → reply to that comment

The score property sums all CommentVote values (upvotes - downvotes).
Computed on access — not stored in the database.

CommentVote stores one vote per user per comment.
  value = 1  → upvote
  value = -1 → downvote
Toggle logic (same vote removes it, opposite vote switches) is in the route.
"""
from datetime import datetime
from .database import db


class Comment(db.Model):
    __tablename__ = "comments"

    id         = db.Column(db.Integer,  primary_key=True)
    content    = db.Column(db.Text,     nullable=False)
    user_id    = db.Column(db.Integer,  db.ForeignKey("users.id",    ondelete="CASCADE"),
                           nullable=False, index=True)
    album_id   = db.Column(db.Integer,  db.ForeignKey("albums.id",   ondelete="CASCADE"),
                           nullable=False, index=True)
    parent_id  = db.Column(db.Integer,  db.ForeignKey("comments.id", ondelete="CASCADE"),
                           nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Self-referential relationship for threading
    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side="Comment.id"),
        lazy="select",
    )

    # Relationships to other models
    author = db.relationship("User",  back_populates="comments")
    album  = db.relationship("Album", back_populates="comments")
    votes  = db.relationship("CommentVote", back_populates="comment",
                             cascade="all, delete-orphan", lazy="select")

    @property
    def score(self) -> int:
        """Upvotes minus downvotes. Computed from loaded votes."""
        return sum(v.value for v in self.votes)

    def __repr__(self) -> str:
        return f"<Comment id={self.id} user={self.user_id} album={self.album_id}>"


class CommentVote(db.Model):
    __tablename__ = "comment_votes"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id",    ondelete="CASCADE"),
                           nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    value      = db.Column(db.Integer, nullable=False)  # 1 or -1

    __table_args__ = (
        db.UniqueConstraint("user_id", "comment_id", name="uq_comment_vote"),
    )

    # Relationships
    voter   = db.relationship("User",    back_populates="comment_votes")
    comment = db.relationship("Comment", back_populates="votes")

    def __repr__(self) -> str:
        return f"<CommentVote user={self.user_id} comment={self.comment_id} value={self.value}>"