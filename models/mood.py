# models/mood.py
# Two models live here:
#
# MoodTag  — the fixed list of all available mood tags (seeded once).
#            Each tag has a name and a category.
#
# AlbumMood — records which user applied which mood tag to which album.
#             This is shared/public — all users' mood choices aggregate
#             on the album detail page and feed into Discovery later.
#
# LIMIT: A user can apply a maximum of 3 mood tags per album (1/5 of 15 total).
# This limit is enforced in the route, not the model.

from .database import db


class MoodTag(db.Model):
    __tablename__ = 'mood_tags'

    id       = db.Column(db.Integer,     primary_key=True)
    name     = db.Column(db.String(50),  unique=True, nullable=False)  # e.g. "Hype"
    category = db.Column(db.String(50),  nullable=False)               # e.g. "Energetic"

    def __repr__(self):
        return f'<MoodTag {self.category} / {self.name}>'


class AlbumMood(db.Model):
    __tablename__ = 'album_moods'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),      nullable=False)
    album_id    = db.Column(db.Integer, db.ForeignKey('albums.id'),     nullable=False)
    mood_tag_id = db.Column(db.Integer, db.ForeignKey('mood_tags.id'),  nullable=False)

    # One user can only apply the same tag to the same album once
    __table_args__ = (
        db.UniqueConstraint('user_id', 'album_id', 'mood_tag_id', name='unique_album_mood'),
    )

    # Easy access to the tag details from an AlbumMood row
    mood_tag = db.relationship('MoodTag', backref='album_moods', lazy=True)

    def __repr__(self):
        return f'<AlbumMood user={self.user_id} album={self.album_id} tag={self.mood_tag_id}>'


# --- Seed data ---
# Call this function once after db.create_all() to populate the mood tags.
# Safe to call multiple times — it checks before inserting.
MOOD_TAGS = [
    # (name, category)
    ('Hype',        'Energetic'),
    ('Party',       'Energetic'),
    ('Pumped',      'Energetic'),

    ('Sad',         'Emotional'),
    ('Melancholic', 'Emotional'),
    ('Reflective',  'Emotional'),

    ('Peaceful',    'Calm'),
    ('Ambient',     'Calm'),
    ('Focused',     'Calm'),

    ('Gritty',      'Dark'),
    ('Moody',       'Dark'),
    ('Intense',     'Dark'),

    ('Warm',        'Romantic'),
    ('Passionate',  'Romantic'),
    ('Dreamy',      'Romantic'),
]

def seed_mood_tags():
    """Insert mood tags into the database if they do not already exist."""
    for name, category in MOOD_TAGS:
        exists = MoodTag.query.filter_by(name=name).first()
        if not exists:
            db.session.add(MoodTag(name=name, category=category))
    db.session.commit()
