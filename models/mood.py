"""
models/mood.py

MoodTag is a fixed lookup table of 15 mood tags across 5 categories.
seed_mood_tags() inserts them on startup — safe to call repeatedly.

AlbumMood links a User, an Album, and a MoodTag.
  - One user can apply up to 3 mood tags per album (enforced in the route).
  - The UniqueConstraint prevents duplicates.
  - Mood data is public — anyone can see the aggregated counts.
"""
from .database import db

# Seed data — 5 categories, 3 tags each
MOOD_SEED = [
    ("Energetic", ["Hype",       "Upbeat",    "Motivating"]),
    ("Emotional", ["Melancholic","Heartfelt", "Nostalgic" ]),
    ("Calm",      ["Relaxing",   "Focused",   "Dreamy"    ]),
    ("Dark",      ["Brooding",   "Intense",   "Haunting"  ]),
    ("Romantic",  ["Sensual",    "Tender",    "Euphoric"  ]),
]


class MoodTag(db.Model):
    __tablename__ = "mood_tags"

    id       = db.Column(db.Integer,    primary_key=True)
    name     = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)

    def __repr__(self) -> str:
        return f"<MoodTag id={self.id} name={self.name!r} category={self.category!r}>"


class AlbumMood(db.Model):
    __tablename__ = "album_moods"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id",      ondelete="CASCADE"),
                            nullable=False)
    album_id    = db.Column(db.Integer, db.ForeignKey("albums.id",     ondelete="CASCADE"),
                            nullable=False)
    mood_tag_id = db.Column(db.Integer, db.ForeignKey("mood_tags.id",  ondelete="CASCADE"),
                            nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "album_id", "mood_tag_id", name="uq_album_mood"),
    )

    # Relationships
    user     = db.relationship("User",    back_populates="album_moods")
    album    = db.relationship("Album",   back_populates="album_moods")
    mood_tag = db.relationship("MoodTag", backref=db.backref("album_moods", lazy="select"))

    def __repr__(self) -> str:
        return (f"<AlbumMood user={self.user_id} "
                f"album={self.album_id} tag={self.mood_tag_id}>")


def seed_mood_tags() -> None:
    """Insert all mood tags if they do not already exist. Safe to call repeatedly."""
    for category, names in MOOD_SEED:
        for name in names:
            if not MoodTag.query.filter_by(name=name).first():
                db.session.add(MoodTag(name=name, category=category))
    db.session.commit()
