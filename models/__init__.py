# models/__init__.py
# This file makes the models folder a Python package and exports
# everything that ecouter.py needs to import in one place.
#
# When you add a new model, import it here and add it to __all__.

from .database import db, init_db
from .user import User
from .album import Album
from .collections import Playlist, collection_albums
from .user_album import UserAlbum, RATING_LIKE, RATING_DISLIKE
from .mood import MoodTag, AlbumMood, seed_mood_tags
from .comment import Comment, CommentVote

__all__ = [
    'db',
    'init_db',
    'User',
    'Album',
    'Playlist',
    'collection_albums',
    'UserAlbum',
    'RATING_LIKE',
    'RATING_DISLIKE',
    'MoodTag',
    'AlbumMood',
    'seed_mood_tags',
    'Comment',
    'CommentVote',
]
