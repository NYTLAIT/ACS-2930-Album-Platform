"""
models/__init__.py

Exports everything ecouter.py needs in one import.
Import order matters — models that reference others must come after them.
"""
from .database    import db, init_db
from .user        import User
from .album       import Album
from .collection  import Collection, collection_albums
from .user_album  import UserAlbum, RATING_LIKE, RATING_DISLIKE
from .mood        import MoodTag, AlbumMood, seed_mood_tags
from .comment     import Comment, CommentVote

__all__ = [
    "db", "init_db",
    "User",
    "Album",
    "Collection", "collection_albums",
    "UserAlbum", "RATING_LIKE", "RATING_DISLIKE",
    "MoodTag", "AlbumMood", "seed_mood_tags",
    "Comment", "CommentVote",
]
