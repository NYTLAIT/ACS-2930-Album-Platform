"""
models/collection.py

A Collection belongs to one User and can contain many Albums.
Albums can belong to many Collections — this is a many-to-many
relationship handled by the collection_albums join table.

collection_albums is a plain Table (not a Model) because we only
need the two foreign key columns and no extra data on the join.

Relationships defined here:
  - owner : the User who created this collection (back_populates User.collections)
  - albums : list of Album objects in this collection
"""
from datetime import datetime
from .database import db


# Join table — no extra columns needed, so we use db.Table not a full Model
collection_albums = db.Table(
    "collection_albums",
    db.Column(
        "collection_id",
        db.Integer,
        db.ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "album_id",
        db.Integer,
        db.ForeignKey("albums.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Collection(db.Model):
    __tablename__ = "collections"

    id             = db.Column(db.Integer,     primary_key=True)
    name           = db.Column(db.String(255), nullable=False)
    description    = db.Column(db.Text,        nullable=True)
    is_public      = db.Column(db.Boolean,     default=False, nullable=False)
    user_id        = db.Column(db.Integer,     db.ForeignKey("users.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    created_at     = db.Column(db.DateTime,    default=datetime.utcnow, nullable=False)
    updated_at     = db.Column(db.DateTime,    default=datetime.utcnow,
                               onupdate=datetime.utcnow, nullable=False)
    last_opened_at = db.Column(db.DateTime,    nullable=True)

    # Relationships
    owner  = db.relationship("User",  back_populates="collections")
    albums = db.relationship(
        "Album",
        secondary=collection_albums,
        backref=db.backref("collections", lazy="select"),
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Collection id={self.id} name={self.name!r} user_id={self.user_id}>"