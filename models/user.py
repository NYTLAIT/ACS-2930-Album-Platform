from sqlalchemy import Column
from sqlalchemy.orm import declarative_base

class Playlist(Base):
    __tablename__ = 'playlists'
    id = Column(Integer, primary_key = True)